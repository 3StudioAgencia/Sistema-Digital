"""Relatorios (W5-C17) contra Postgres REAL (@db).

Exercita o caminho HTTP inteiro como em producao (``SET LOCAL ROLE authenticated``
+ claims — ADR-008/ADR-034), validando:

- a nova funcao de HORAS UTEIS ``private.horas_uteis_entre`` (atravessa noite/fim de
  semana; janela 07-18; America/Sao_Paulo) — migration 0021;
- as 4 abas (DP-1/§0.2) com as FORMULAS confirmadas (DP-3): tempo medio de
  aprovacao (chegada->aprovacao), taxa de reprovacao, distribuicao por rota
  (SOMA 100% — criterio §6.3), atrasadas (MESMA regra do C16 — §6.5), devolvidas
  (=reprovacoes), tempo medio aguardando da clicheria, etc.;
- ACESSO exclusivo 3Studio (flag admin) em 2 camadas → 403 ao nao-admin nos
  endpoints de agregacao E de export (DP-7);
- FILTROS compartilhados (periodo/status/rota multi/vendedor) — DP-4;
- CSV (DP-5): text/csv, BOM, preserva campos, respeita filtros.
"""

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from src.adapters.inbound.http.auth import JwtVerifier
from src.domain.provas import gerar_codigo
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"
TZ3 = dt.timezone(dt.timedelta(hours=-3))  # America/Sao_Paulo (sem DST desde 2019)


def _brt(dia: int, hora: int) -> dt.datetime:
    """Instante em junho/2026 no fuso comercial (-03). 15 = Seg, 12 = Sex."""
    return dt.datetime(2026, 6, dia, hora, 0, tzinfo=TZ3)


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


async def _seed_usuario(
    engine: AsyncEngine, *, setor: str, nome: str, admin: bool = False, loc: str | None = None
) -> str:
    uid = str(uuid.uuid4())
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
                "VALUES (:id, :codigo, 'Ricota fresca', '150150', 'Laticinios Artvac', :vendedor, "
                ":rota, :status, 'provas/x/arte.png', 'image/png', "
                "COALESCE(:created_at, now()), :fin)"
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


async def _seed_mov(
    engine: AsyncEngine,
    *,
    prova_id: str,
    ator_id: str,
    acao: str,
    origem: str,
    destino: str,
    quando: dt.datetime,
    motivo: str | None = None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO movimentacoes (id, prova_id, estado_origem, estado_destino, acao, "
                "ator_id, ciclo, motivo, idempotency_key, created_at) "
                "VALUES (:id, :prova, :origem, :destino, :acao, :ator, 1, :motivo, :idem, :quando)"
            ),
            {
                "id": str(uuid.uuid4()),
                "prova": prova_id,
                "origem": origem,
                "destino": destino,
                "acao": acao,
                "ator": ator_id,
                "motivo": motivo,
                "idem": str(uuid.uuid4()),
                "quando": quando,
            },
        )


# ---------------------------------------------------------------------------
# Funcao de horas uteis — chamada DIRETA (como owner; EXECUTE livre)
# ---------------------------------------------------------------------------
async def _horas(engine: AsyncEngine, ini: dt.datetime, fim: dt.datetime) -> float:
    async with engine.connect() as conn:
        valor = (
            await conn.execute(
                text("SELECT private.horas_uteis_entre(:ini, :fim)"),
                {"ini": ini, "fim": fim},
            )
        ).scalar_one()
    return float(valor)


@pytest.mark.parametrize(
    ("ini", "fim", "esperado"),
    [
        # Seg 09:00 -> Seg 11:00 = 2h uteis (dentro da janela).
        (_brt(15, 9), _brt(15, 11), 2.0),
        # Seg 09:00 -> Seg 20:00 = 9h (07-18 cobre 09-18; tarde apos 18 nao conta).
        (_brt(15, 9), _brt(15, 20), 9.0),
        # Sex 17:00 -> Seg 08:00 = 1h (Sex 17-18) + 1h (Seg 07-08); fim de semana pulado.
        (_brt(12, 17), _brt(15, 8), 2.0),
        # Mesmo instante / invertido -> 0.
        (_brt(15, 9), _brt(15, 9), 0.0),
        (_brt(15, 11), _brt(15, 9), 0.0),
    ],
)
async def test_horas_uteis_entre(
    usuarios_engine: AsyncEngine, ini: dt.datetime, fim: dt.datetime, esperado: float
) -> None:
    assert await _horas(usuarios_engine, ini, fim) == pytest.approx(esperado)


# ---------------------------------------------------------------------------
# Cenario compartilhado
# ---------------------------------------------------------------------------
@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, str]]]:
    engine = usuarios_engine
    admin = await _seed_usuario(engine, setor="studio", nome="Monica", admin=True)
    mario = await _seed_usuario(engine, setor="vendedor", nome="Mario Souza", loc="filial")
    andre = await _seed_usuario(engine, setor="vendedor", nome="Andre Bento", loc="matriz")

    agora = dt.datetime.now(tz=dt.UTC)
    velho = agora - dt.timedelta(days=30)  # alem de 48h uteis
    seg9, seg11, seg13 = _brt(15, 9), _brt(15, 11), _brt(15, 13)

    # P_aprovada (Mario/filial): chegada 09:00 -> aprovacao 11:00 = 2h uteis.
    p_aprov = await _seed_prova(
        engine, vendedor_id=mario, status="aprovada_vendedor", rota="filial"
    )
    await _seed_mov(engine, prova_id=p_aprov, ator_id=mario, acao="identificar_e_assinar",
                    origem="criada", destino="encaminhada_para_vendedor", quando=seg9)
    await _seed_mov(engine, prova_id=p_aprov, ator_id=mario, acao="aprovar",
                    origem="encaminhada_para_vendedor", destino="aprovada_vendedor", quando=seg11)

    # P_reprovada (Mario/matriz): conta como reprovada ATIVA + devolvida (evento).
    p_reprov = await _seed_prova(
        engine, vendedor_id=mario, status="reprovada_vendedor", rota="matriz"
    )
    await _seed_mov(engine, prova_id=p_reprov, ator_id=mario, acao="identificar_e_assinar",
                    origem="criada", destino="retirada_vendedor", quando=seg9)
    await _seed_mov(engine, prova_id=p_reprov, ator_id=mario, acao="reprovar",
                    origem="retirada_vendedor", destino="reprovada_vendedor", quando=seg11,
                    motivo="Cor divergente")

    # P_atrasada (Andre/filial): ativa, parada ha 30 dias -> atrasada (regra C16).
    await _seed_prova(engine, vendedor_id=andre, status="retirada_vendedor", rota="filial",
                      created_at=velho)

    # P_recebida (Mario/lam_matriz): envio 09:00 -> recebimento 13:00 = 4h uteis.
    p_receb = await _seed_prova(engine, vendedor_id=mario, status="recebida_clicheria",
                                rota="lam_matriz", finalizada_em=agora)
    await _seed_mov(engine, prova_id=p_receb, ator_id=mario, acao="identificar_e_assinar",
                    origem="de_volta_studio", destino="com_motorista_entrega_final", quando=seg9)
    await _seed_mov(engine, prova_id=p_receb, ator_id=mario, acao="identificar_e_assinar",
                    origem="com_motorista_entrega_final", destino="recebida_clicheria",
                    quando=seg13)

    # P_em_transito (Andre/matriz): rumo a clicheria agora.
    await _seed_prova(engine, vendedor_id=andre, status="com_motorista_entrega_final",
                      rota="matriz")

    # P_cancelada (Mario/matriz): cancelamento com motivo (top motivos).
    p_canc = await _seed_prova(engine, vendedor_id=mario, status="cancelada", rota="matriz",
                               finalizada_em=agora)
    await _seed_mov(engine, prova_id=p_canc, ator_id=admin, acao="cancelar",
                    origem="criada", destino="cancelada", quando=seg11, motivo="Apenas Teste")

    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    ids = {"admin": admin, "mario": mario, "andre": andre}
    async with client as c:
        yield c, engine, ids


async def _get(client: httpx.AsyncClient, path: str, auth: dict[str, str]) -> dict[str, Any]:
    resp = await client.get(path, headers=auth)
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    return body


# ---------------------------------------------------------------------------
# Aba Geral
# ---------------------------------------------------------------------------
async def test_geral_totais_e_distribuicao_soma_100(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(client, "/relatorios/geral", _auth(ids["admin"], "studio", True))
    assert body["total_geral"] == 6
    # Distribuicao SOMA o total (criterio §6.3: 100% no periodo).
    soma = sum(f["total"] for f in body["distribuicao_rota"])
    assert soma == body["total_geral"]
    por_rota = {f["rota"]: f["total"] for f in body["distribuicao_rota"]}
    assert por_rota == {"matriz": 3, "lam_matriz": 1, "filial": 2, "lam_filial": 0}


async def test_geral_tempo_medio_e_taxa(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(client, "/relatorios/geral", _auth(ids["admin"], "studio", True))
    # Unica aprovacao: chegada 09:00 -> aprovacao 11:00 = 2h uteis.
    assert body["tempo_medio_aprovacao_horas"] == pytest.approx(2.0)
    # 1 aprovacao + 1 reprovacao -> 50%.
    assert body["taxa_reprovacao"] == pytest.approx(50.0)
    assert body["ativas_aguardando_vendedor"] == 1  # so a P_atrasada (retirada)
    assert body["ativas_reprovadas"] == 1


async def test_geral_atrasadas_consistente_com_c16(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(client, "/relatorios/geral", _auth(ids["admin"], "studio", True))
    # So a P_atrasada (ativa, parada 30 dias). Terminais (recebida/cancelada) excluidos.
    assert len(body["provas_atrasadas"]) == 1
    linha = body["provas_atrasadas"][0]
    assert linha["vendedor_nome"] == "Andre Bento"
    assert linha["atraso_horas"] > 0


async def test_geral_metricas_por_vendedor(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(client, "/relatorios/geral", _auth(ids["admin"], "studio", True))
    por_nome = {m["vendedor_nome"]: m for m in body["metricas_por_vendedor"]}
    assert por_nome["Mario Souza"]["volume"] == 4  # aprov + reprov + receb + canc
    assert por_nome["Mario Souza"]["aprovadas"] == 1
    assert por_nome["Mario Souza"]["reprovadas"] == 1
    assert por_nome["Mario Souza"]["taxa_reprovacao"] == pytest.approx(50.0)
    assert por_nome["Mario Souza"]["atrasadas"] == 0
    assert por_nome["Andre Bento"]["volume"] == 2
    assert por_nome["Andre Bento"]["atrasadas"] == 1  # P_atrasada
    # Ordenado por volume desc.
    assert body["metricas_por_vendedor"][0]["vendedor_nome"] == "Mario Souza"


# ---------------------------------------------------------------------------
# Aba 3Studio
# ---------------------------------------------------------------------------
async def test_studio_eventos_e_motivos(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(client, "/relatorios/studio", _auth(ids["admin"], "studio", True))
    assert body["provas_criadas"] == 6
    assert body["devolvidas"] == 1  # 1 reprovacao (DP-3)
    assert body["cancelamentos"] == 1
    assert body["reinicios_ciclo"] == 0
    assert body["reprovadas_aguardando"] == 1
    assert body["top_motivos_cancelamento"] == [{"motivo": "Apenas Teste", "total": 1}]
    assert body["tempo_ate_primeira_mov_horas"] is not None


# ---------------------------------------------------------------------------
# Aba Vendedores
# ---------------------------------------------------------------------------
async def test_vendedores_contagens(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(client, "/relatorios/vendedores", _auth(ids["admin"], "studio", True))
    assert body["vendedores_filial"] == 1  # Mario
    assert body["vendedores_matriz"] == 1  # Andre
    assert body["vendedores_ativos"] == 2  # ambos tem prova no periodo
    assert body["atrasadas_total"] == 1
    assert {m["vendedor_nome"] for m in body["por_vendedor"]} == {"Mario Souza", "Andre Bento"}


# ---------------------------------------------------------------------------
# Aba Clicheria
# ---------------------------------------------------------------------------
async def test_clicheria_perspectiva_rumo_a_clicheria(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(client, "/relatorios/clicheria", _auth(ids["admin"], "studio", True))
    assert body["recebidas_no_periodo"] == 1
    assert body["em_transito_agora"] == 1
    assert body["origens"] == 1  # so lam_matriz entre as recebidas
    # Envio 09:00 -> recebimento 13:00 = 4h uteis.
    assert body["tempo_medio_aguardando_horas"] == pytest.approx(4.0)
    origem = {f["rota"]: f["total"] for f in body["distribuicao_origem"]}
    assert origem["lam_matriz"] == 1


# ---------------------------------------------------------------------------
# Filtros (DP-4)
# ---------------------------------------------------------------------------
async def test_filtro_rota_multivalor_agrupado(ctx: tuple[Any, ...]) -> None:
    """Toggle 2-vias "Matriz" manda rota=matriz&rota=lam_matriz (DP-4)."""
    client, _, ids = ctx
    body = await _get(
        client, "/relatorios/geral?rota=matriz&rota=lam_matriz", _auth(ids["admin"], "studio", True)
    )
    assert body["total_geral"] == 4  # matriz(3) + lam_matriz(1)


async def test_filtro_vendedor_e_status(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _get(
        client, f"/relatorios/geral?vendedor_id={ids['andre']}", _auth(ids["admin"], "studio", True)
    )
    assert body["total_geral"] == 2
    body2 = await _get(
        client, "/relatorios/geral?status=reprovada_vendedor", _auth(ids["admin"], "studio", True)
    )
    assert body2["total_geral"] == 1


async def test_filtro_periodo_exclui_provas_antigas(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    hoje = dt.datetime.now(tz=dt.UTC).date().isoformat()
    body = await _get(client, f"/relatorios/geral?de={hoje}", _auth(ids["admin"], "studio", True))
    assert body["total_geral"] == 5  # exclui a P_atrasada (criada ha 30 dias)


# ---------------------------------------------------------------------------
# Acesso 3Studio (DP-7) + CSV (DP-5)
# ---------------------------------------------------------------------------
async def test_nao_admin_recebe_403_em_todas_as_abas_e_export(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    auth = _auth(ids["mario"], "vendedor")
    for path in ("/relatorios/geral", "/relatorios/studio", "/relatorios/vendedores",
                 "/relatorios/clicheria", "/relatorios/exportar?aba=geral"):
        resp = await client.get(path, headers=auth)
        assert resp.status_code == 403, path
        assert resp.json()["error"]["message"] == "Acesso negado."


async def test_sem_token_401(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    assert (await client.get("/relatorios/geral")).status_code == 401


async def test_export_csv_bom_e_campos(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    resp = await client.get(
        "/relatorios/exportar?aba=geral", headers=_auth(ids["admin"], "studio", True)
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"\xef\xbb\xbf")  # BOM (Excel pt-BR)
    texto = resp.content.decode("utf-8-sig")
    assert "Total geral;6" in texto
    assert "Mario Souza" in texto


async def test_export_csv_respeita_filtros(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    resp = await client.get(
        "/relatorios/exportar?aba=geral&rota=filial", headers=_auth(ids["admin"], "studio", True)
    )
    texto = resp.content.decode("utf-8-sig")
    assert "Total geral;2" in texto  # so filial (aprov + atrasada)
