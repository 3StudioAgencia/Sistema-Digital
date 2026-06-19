"""GET /dashboard (W4-C16) contra Postgres REAL (@db).

Exercita o caminho HTTP inteiro como em produção (``SET LOCAL ROLE authenticated``
+ claims propagados — ADR-008/ADR-034), validando:

- a função de HORAS ÚTEIS ``private.instante_limite_atraso`` (atravessa noite/fim
  de semana; janela 07-18; fuso America/Sao_Paulo) — DP-4;
- os 5 contadores do design (DP-1/DP-2): Criadas hoje, Com Vendedor, Aprovadas,
  Na clicheria, Atrasadas;
- "Atrasada" = prova ATIVA parada além do limiar (base na ÚLTIMA movimentação,
  não no created_at) e EXCLUI terminais;
- o breakdown de "Atrasadas" por vendedor + total, ORDENADO por contagem desc;
- ESCOPO por perfil via RLS (Matriz §7): 3Studio/Admin todas, Vendedor só as suas
  (e só a si no breakdown), Motorista só "Em Trânsito";
- a agregação é UMA consulta (sem N+1 — RNF-022): o nº de SELECTs em ``provas`` é
  constante (1), independente do nº de linhas/vendedores.
"""

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine
from src.adapters.inbound.http.auth import JwtVerifier
from src.domain.provas import gerar_codigo
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
TZ3 = dt.timezone(dt.timedelta(hours=-3))  # America/Sao_Paulo (sem DST desde 2019)


def _token(sub: str, setor: str, administrador: bool = False) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": sub,
        "user_id": sub,
        "email": "x@y.z",
        "setor": setor,
        "administrador": administrador,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    return jwt.encode(claims, HS256_SECRET, algorithm="HS256")


def _auth(sub: str, setor: str, admin: bool = False) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(sub, setor, admin)}"}


async def _seed_usuario(engine: AsyncEngine, *, setor: str, nome: str, admin: bool = False) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, :nome, :email, :setor, :loc, :adm)"
            ),
            {
                "id": uid,
                "nome": nome,
                "email": f"{uid}@x.z",
                "setor": setor,
                "loc": loc,
                "adm": admin,
            },
        )
    return uid


async def _seed_prova(
    engine: AsyncEngine,
    *,
    vendedor_id: str,
    status: str,
    rota: str = "matriz",
    created_at: dt.datetime | None = None,
    finalizada_em: dt.datetime | None = None,
) -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type, created_at, finalizada_em) "
                "VALUES (:id, :codigo, 'Etiqueta', '155295', 'Cafe Caproni', :vendedor, :rota, "
                ":status, 'provas/x/arte.png', 'image/png', COALESCE(:created_at, now()), :fin)"
            ),
            {
                "id": uid,
                "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)),
                "vendedor": vendedor_id,
                "rota": rota,
                "status": status,
                "created_at": created_at,
                "fin": finalizada_em,
            },
        )
    return uid


async def _seed_movimentacao(
    engine: AsyncEngine, *, prova_id: str, ator_id: str, quando: dt.datetime
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO movimentacoes (id, prova_id, estado_origem, estado_destino, acao, "
                "ator_id, ciclo, idempotency_key, created_at) "
                "VALUES (:id, :prova, 'criada', 'retirada_vendedor', 'identificar_e_assinar', "
                ":ator, 1, :idem, :quando)"
            ),
            {
                "id": str(uuid.uuid4()),
                "prova": prova_id,
                "ator": ator_id,
                "idem": str(uuid.uuid4()),
                "quando": quando,
            },
        )


# ---------------------------------------------------------------------------
# Função de horas úteis — chamada DIRETA (como owner; EXECUTE livre)
# ---------------------------------------------------------------------------
async def _limite(engine: AsyncEngine, agora: dt.datetime, horas: int) -> dt.datetime:
    async with engine.connect() as conn:
        valor = (
            await conn.execute(
                text("SELECT private.instante_limite_atraso(:agora, :horas)"),
                {"agora": agora, "horas": horas},
            )
        ).scalar_one()
    assert isinstance(valor, dt.datetime)
    return valor


@pytest.mark.parametrize(
    ("agora", "horas", "esperado"),
    [
        # Seg 10:00 - 2h úteis = Seg 08:00 (dentro da janela).
        (
            dt.datetime(2026, 6, 15, 10, 0, tzinfo=TZ3),
            2,
            dt.datetime(2026, 6, 15, 8, 0, tzinfo=TZ3),
        ),
        # Seg 08:00 - 2h: 1h hoje (07-08) + 1h sexta (17-18) = Sex 17:00 (cruza fim de semana).
        (
            dt.datetime(2026, 6, 15, 8, 0, tzinfo=TZ3),
            2,
            dt.datetime(2026, 6, 12, 17, 0, tzinfo=TZ3),
        ),
        # Seg 20:00 (após expediente) - 3h = Seg 15:00 (colapsa ao fim da janela 18:00).
        (
            dt.datetime(2026, 6, 15, 20, 0, tzinfo=TZ3),
            3,
            dt.datetime(2026, 6, 15, 15, 0, tzinfo=TZ3),
        ),
        # Sáb 10:00 - 1h: fim de semana não conta = Sex 17:00.
        (
            dt.datetime(2026, 6, 13, 10, 0, tzinfo=TZ3),
            1,
            dt.datetime(2026, 6, 12, 17, 0, tzinfo=TZ3),
        ),
        # Seg 12:00 - 48h úteis (4d cheios + 5h) = Ter anterior 08:00 (pula o fim de semana).
        (
            dt.datetime(2026, 6, 15, 12, 0, tzinfo=TZ3),
            48,
            dt.datetime(2026, 6, 9, 8, 0, tzinfo=TZ3),
        ),
    ],
)
async def test_instante_limite_atraso_horas_uteis(
    usuarios_engine: AsyncEngine, agora: dt.datetime, horas: int, esperado: dt.datetime
) -> None:
    assert await _limite(usuarios_engine, agora, horas) == esperado


# ---------------------------------------------------------------------------
# Cenário de contadores
# ---------------------------------------------------------------------------
@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, Any]]]:
    engine = usuarios_engine
    admin = await _seed_usuario(engine, setor="studio", nome="Monica", admin=True)
    studio = await _seed_usuario(engine, setor="studio", nome="Studio Op")  # não-admin (DP-7)
    motorista = await _seed_usuario(engine, setor="motorista", nome="Moto Op")
    regiane = await _seed_usuario(engine, setor="vendedor", nome="Regiane")
    packon = await _seed_usuario(engine, setor="vendedor", nome="Packon")

    velho = dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=30)  # bem além de 48h úteis

    # Criadas HOJE (created_at = now()): 1 da Regiane + 1 do Packon (em trânsito).
    await _seed_prova(engine, vendedor_id=regiane, status="criada")
    await _seed_prova(
        engine, vendedor_id=packon, status="com_motorista_ida_laminacao", rota="lam_matriz"
    )
    # Com Vendedor (posse): retirada (Regiane) + encaminhada (Packon) — VELHAS = atrasadas.
    await _seed_prova(engine, vendedor_id=regiane, status="retirada_vendedor", created_at=velho)
    await _seed_prova(
        engine,
        vendedor_id=packon,
        status="encaminhada_para_vendedor",
        rota="filial",
        created_at=velho,
    )
    # Aprovada (Packon) — VELHA = atrasada.
    await _seed_prova(
        engine, vendedor_id=packon, status="aprovada_vendedor", rota="filial", created_at=velho
    )
    # Na clicheria (terminal) — VELHA mas NÃO atrasada (terminal excluído).
    await _seed_prova(
        engine,
        vendedor_id=packon,
        status="recebida_clicheria",
        created_at=velho,
        finalizada_em=dt.datetime.now(tz=dt.UTC),
    )
    # Retirada VELHA mas com movimentação RECENTE → último evento recente → NÃO atrasada
    # (prova a base de atraso na ÚLTIMA movimentação, não no created_at).
    p_movida = await _seed_prova(
        engine, vendedor_id=regiane, status="retirada_vendedor", created_at=velho
    )
    await _seed_movimentacao(
        engine, prova_id=p_movida, ator_id=regiane, quando=dt.datetime.now(tz=dt.UTC)
    )

    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    ids = {
        "admin": admin,
        "studio": studio,
        "motorista": motorista,
        "regiane": regiane,
        "packon": packon,
    }
    async with client as c:
        yield c, engine, ids


async def _dash(client: httpx.AsyncClient, auth: dict[str, str]) -> dict[str, Any]:
    resp = await client.get("/dashboard", headers=auth)
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    return body


async def test_admin_ve_todos_os_contadores(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _dash(client, _auth(ids["admin"], "studio", True))
    assert body["criadas_hoje"] == 2  # 1 Regiane + 1 Packon (em trânsito), hoje
    assert body["com_vendedor"] == 3  # retirada(velha) + retirada(movida) + encaminhada(velha)
    assert body["aprovadas"] == 1
    assert body["na_clicheria"] == 1


async def test_atrasadas_breakdown_ordenado_e_exclui_terminais_e_movidas(
    ctx: tuple[Any, ...],
) -> None:
    """Atrasadas: só ATIVAS, paradas além do limiar, base na ÚLTIMA movimentação.
    Packon 2 (encaminhada+aprovada), Regiane 1 (retirada velha). A terminal e a
    movida-recente NÃO contam. Lista ordenada por contagem desc."""
    client, _, ids = ctx
    body = await _dash(client, _auth(ids["admin"], "studio", True))
    assert body["atrasadas_total"] == 3
    bd = body["atrasadas_por_vendedor"]
    assert [(b["vendedor_nome"], b["total"]) for b in bd] == [("Packon", 2), ("Regiane", 1)]


async def test_studio_nao_admin_resolve_nomes_no_breakdown(ctx: tuple[Any, ...]) -> None:
    """DP-7: a RLS de usuarios bloquearia um JOIN; a projeção SECURITY DEFINER
    resolve o nome do vendedor para o 3Studio NÃO-admin."""
    client, _, ids = ctx
    body = await _dash(client, _auth(ids["studio"], "studio", False))
    assert {b["vendedor_nome"] for b in body["atrasadas_por_vendedor"]} == {"Packon", "Regiane"}


async def test_vendedor_ve_apenas_os_seus_numeros(ctx: tuple[Any, ...]) -> None:
    """Escopo por RLS: Regiane vê só as 3 provas dela; breakdown só com ela."""
    client, _, ids = ctx
    body = await _dash(client, _auth(ids["regiane"], "vendedor"))
    assert body["criadas_hoje"] == 1  # só a criada-hoje da Regiane
    assert body["com_vendedor"] == 2  # retirada(velha) + retirada(movida)
    assert body["aprovadas"] == 0
    assert body["na_clicheria"] == 0
    assert body["atrasadas_total"] == 1
    assert [(b["vendedor_nome"], b["total"]) for b in body["atrasadas_por_vendedor"]] == [
        ("Regiane", 1)
    ]


async def test_motorista_ve_apenas_em_transito(ctx: tuple[Any, ...]) -> None:
    """Motorista enxerga só ESTADOS_ESCOPO_MOTORISTA: a única visível é a em-trânsito
    de hoje — os demais contadores zeram, atrasadas vazia."""
    client, _, ids = ctx
    body = await _dash(client, _auth(ids["motorista"], "motorista"))
    assert body["criadas_hoje"] == 1  # a com_motorista_ida_laminacao criada hoje
    assert body["com_vendedor"] == 0
    assert body["aprovadas"] == 0
    assert body["na_clicheria"] == 0
    assert body["atrasadas_total"] == 0
    assert body["atrasadas_por_vendedor"] == []


async def test_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.get("/dashboard")
    assert resp.status_code == 401


async def test_usuario_nao_provisionado_recebe_403_generico(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.get("/dashboard", headers=_auth(str(uuid.uuid4()), "studio", True))
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Acesso negado."


async def test_agregacao_e_consulta_unica_sem_n_mais_1(ctx: tuple[Any, ...]) -> None:
    """RNF-022: a contagem em ``provas`` é UMA, independente do nº de linhas."""
    client, engine, ids = ctx
    sqls: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _coletar(conn: Any, cursor: Any, statement: str, *_a: Any) -> None:
        sqls.append(statement.lower())

    sqls.clear()
    await _dash(client, _auth(ids["admin"], "studio", True))
    event.remove(engine.sync_engine, "before_cursor_execute", _coletar)

    # 1 statement de agregação toca ``provas`` (o gate lê ``usuarios``, não provas).
    de_provas = sum(1 for s in sqls if "from provas" in s)
    assert de_provas == 1
