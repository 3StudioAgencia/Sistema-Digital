"""GET /provas (listagem W2-C07) contra Postgres REAL (@db).

Exercita o caminho HTTP inteiro como em produção (``SET LOCAL ROLE authenticated``
+ claims propagados — ADR-008/ADR-034), validando:

- ESCOPO por perfil na RLS (Matriz §7): 3Studio/Clicheria/Admin todas, Vendedor as
  suas, Motorista as "Em Trânsito"; query fora do escopo → 0 registros;
- o NOME do vendedor resolve até para um 3Studio NÃO-admin / Motorista (DP-7: a
  RLS de ``usuarios`` os bloquearia num JOIN — a função SECURITY DEFINER resolve);
- filtros combináveis (status, rota, vendedor, cliente, busca, períodos) e
  paginação server-side ordenada por ``created_at`` desc;
- ausência de N+1 (nº de SELECTs em ``provas`` e de chamadas ao projetor é
  constante, independente do nº de linhas);
- a página é UNIVERSAL (qualquer perfil ativo), não gateada a admin.
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
    engine: AsyncEngine, *, setor: str, nome: str, administrador: bool = False
) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, :nome, :email, :setor, :loc, :adm)"
            ),
            {"id": uid, "nome": nome, "email": f"{uid}@x.z", "setor": setor, "loc": loc,
             "adm": administrador},
        )
    return uid


async def _seed_prova(
    engine: AsyncEngine,
    *,
    vendedor_id: str,
    status: str = "criada",
    rota: str = "matriz",
    nome: str = "Etiqueta granola",
    requerimento: str = "155295",
    cliente: str = "Cafe Caproni",
    created_at: dt.datetime | None = None,
    finalizada_em: dt.datetime | None = None,
) -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type, created_at, finalizada_em) "
                "VALUES (:id, :codigo, :nome, :req, :cliente, :vendedor, :rota, :status, "
                "'provas/x/arte.png', 'image/png', COALESCE(:created_at, now()), :finalizada_em)"
            ),
            {
                "id": uid,
                "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)),
                "nome": nome,
                "req": requerimento,
                "cliente": cliente,
                "vendedor": vendedor_id,
                "rota": rota,
                "status": status,
                "created_at": created_at,
                "finalizada_em": finalizada_em,
            },
        )
    return uid


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, Any]]]:
    engine = usuarios_engine
    admin = await _seed_usuario(engine, setor="studio", nome="Monica", administrador=True)
    studio = await _seed_usuario(engine, setor="studio", nome="Studio Op")  # NÃO-admin (DP-7)
    clicheria = await _seed_usuario(engine, setor="clicheria", nome="Cliche Op")
    motorista = await _seed_usuario(engine, setor="motorista", nome="Moto Op")
    regiane = await _seed_usuario(engine, setor="vendedor", nome="Regiane")
    packon = await _seed_usuario(engine, setor="vendedor", nome="Packon")

    base = dt.datetime(2026, 4, 9, 12, 0, tzinfo=dt.UTC)
    p_criada_reg = await _seed_prova(engine, vendedor_id=regiane, created_at=base)
    p_ida_reg = await _seed_prova(
        engine, vendedor_id=regiane, status="com_motorista_ida_laminacao",
        rota="lam_matriz", created_at=base + dt.timedelta(hours=1),
    )
    p_aprovada_pack = await _seed_prova(
        engine, vendedor_id=packon, status="aprovada_vendedor", rota="filial",
        cliente="Cocatrel", nome="Embalagem premium", requerimento="998877",
        created_at=base + dt.timedelta(hours=2),
    )
    p_clicheria_pack = await _seed_prova(
        engine, vendedor_id=packon, status="recebida_clicheria",
        created_at=base + dt.timedelta(hours=3),
        finalizada_em=dt.datetime(2026, 4, 12, 9, 0, tzinfo=dt.UTC),
    )

    ids = {
        "admin": admin, "studio": studio, "clicheria": clicheria, "motorista": motorista,
        "regiane": regiane, "packon": packon,
        "todas": {p_criada_reg, p_ida_reg, p_aprovada_pack, p_clicheria_pack},
        "de_regiane": {p_criada_reg, p_ida_reg},
        "de_packon": {p_aprovada_pack, p_clicheria_pack},
        "em_transito": {p_ida_reg},
        "p_aprovada_pack": p_aprovada_pack,
        "p_clicheria_pack": p_clicheria_pack,
    }
    client = make_client(
        settings, FakeStorage(), ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, engine, ids


async def _listar(client: httpx.AsyncClient, auth: dict[str, str], **params: Any) -> dict[str, Any]:
    resp = await client.get("/provas", params=params, headers=auth)
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    return body


def _ids(body: dict[str, Any]) -> set[str]:
    return {item["id"] for item in body["items"]}


# ---------------------------------------------------------------------------
# Escopo por perfil (Matriz §7 a nível de dado, via RLS)
# ---------------------------------------------------------------------------
async def test_admin_studio_ve_todas(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(client, _auth(ids["admin"], "studio", True))
    assert _ids(body) == ids["todas"]
    assert body["total"] == 4


async def test_studio_nao_admin_ve_todas_e_resolve_nome_do_vendedor(ctx: tuple[Any, ...]) -> None:
    """DP-7: a RLS de usuarios bloquearia um JOIN; a função SECURITY DEFINER
    resolve o nome do vendedor para o 3Studio NÃO-admin."""
    client, _, ids = ctx
    body = await _listar(client, _auth(ids["studio"], "studio", False))
    assert _ids(body) == ids["todas"]
    nomes = {item["vendedor_nome"] for item in body["items"]}
    assert nomes == {"Regiane", "Packon"}  # nenhum None — nomes resolvidos


async def test_clicheria_ve_todas(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(client, _auth(ids["clicheria"], "clicheria"))
    assert _ids(body) == ids["todas"]


async def test_vendedor_ve_apenas_as_proprias(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(client, _auth(ids["regiane"], "vendedor"))
    assert _ids(body) == ids["de_regiane"]
    assert all(item["vendedor_nome"] == "Regiane" for item in body["items"])


async def test_motorista_ve_apenas_em_transito_com_nome(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(client, _auth(ids["motorista"], "motorista"))
    assert _ids(body) == ids["em_transito"]
    assert body["items"][0]["vendedor_nome"] == "Regiane"  # DP-7 também p/ motorista


async def test_vendedor_provisionado_sem_provas_recebe_zero(ctx: tuple[Any, ...]) -> None:
    """§6.6 no HTTP: vendedor LEGÍTIMO sem provas → 200 com 0 registros (a RLS
    escopa para vazio). O sub não provisionado é outro caso (403, testado à parte)."""
    client, engine, _ = ctx
    novato = await _seed_usuario(engine, setor="vendedor", nome="Novato")
    body = await _listar(client, _auth(novato, "vendedor"))
    assert body["items"] == [] and body["total"] == 0


# ---------------------------------------------------------------------------
# Filtros combináveis (RF-014/US-012) — sempre dentro do escopo
# ---------------------------------------------------------------------------
async def test_filtro_status(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(client, _auth(ids["admin"], "studio", True), status="aprovada_vendedor")
    assert _ids(body) == {ids["p_aprovada_pack"]}


async def test_filtro_rota_e_vendedor_combinados(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(
        client, _auth(ids["admin"], "studio", True), rota="filial", vendedor_id=ids["packon"]
    )
    assert _ids(body) == {ids["p_aprovada_pack"]}


async def test_busca_por_requerimento_e_por_nome(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    por_req = await _listar(client, _auth(ids["admin"], "studio", True), busca="998877")
    assert _ids(por_req) == {ids["p_aprovada_pack"]}
    por_nome = await _listar(client, _auth(ids["admin"], "studio", True), busca="premium")
    assert _ids(por_nome) == {ids["p_aprovada_pack"]}


async def test_filtro_cliente_contains(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(client, _auth(ids["admin"], "studio", True), cliente="cocat")
    assert _ids(body) == {ids["p_aprovada_pack"]}


async def test_filtro_finalizada_em_exclui_sem_carimbo(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    body = await _listar(
        client, _auth(ids["admin"], "studio", True),
        finalizada_de="2026-04-12", finalizada_ate="2026-04-12",
    )
    assert _ids(body) == {ids["p_clicheria_pack"]}  # só a finalizada nesse dia


async def test_filtro_criada_em_periodo(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    # todas foram criadas em 2026-04-09 (limite de dia inclusivo)
    dentro = await _listar(
        client, _auth(ids["admin"], "studio", True), criada_de="2026-04-09", criada_ate="2026-04-09"
    )
    assert _ids(dentro) == ids["todas"]
    fora = await _listar(client, _auth(ids["admin"], "studio", True), criada_de="2026-04-10")
    assert fora["items"] == []


# ---------------------------------------------------------------------------
# Paginação server-side + ordenação
# ---------------------------------------------------------------------------
async def test_paginacao_e_ordenacao_desc(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    pg1 = await _listar(client, _auth(ids["admin"], "studio", True), page=1, page_size=2)
    assert len(pg1["items"]) == 2 and pg1["total"] == 4
    # mais recente primeiro: a recebida_clicheria (base+3h) abre a página
    assert pg1["items"][0]["id"] == ids["p_clicheria_pack"]
    pg2 = await _listar(client, _auth(ids["admin"], "studio", True), page=2, page_size=2)
    assert len(pg2["items"]) == 2
    assert _ids(pg1).isdisjoint(_ids(pg2))  # páginas sem sobreposição
    assert _ids(pg1) | _ids(pg2) == ids["todas"]


async def test_page_size_acima_do_teto_e_422(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    resp = await client.get(
        "/provas", params={"page_size": 9999}, headers=_auth(ids["admin"], "studio", True)
    )
    assert resp.status_code == 422  # le=PAGE_SIZE_MAXIMO


# ---------------------------------------------------------------------------
# Dropdown de vendedores (escopado) e gate universal
# ---------------------------------------------------------------------------
async def test_vendedores_endpoint_lista_distintos_em_escopo(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    resp = await client.get("/provas/vendedores", headers=_auth(ids["admin"], "studio", True))
    assert resp.status_code == 200
    nomes = [v["nome"] for v in resp.json()]
    assert nomes == ["Packon", "Regiane"]  # ordenado por nome


async def test_vendedores_endpoint_para_vendedor_so_ele_mesmo(ctx: tuple[Any, ...]) -> None:
    client, _, ids = ctx
    resp = await client.get("/provas/vendedores", headers=_auth(ids["regiane"], "vendedor"))
    assert [v["nome"] for v in resp.json()] == ["Regiane"]


async def test_listagem_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.get("/provas")
    assert resp.status_code == 401


async def test_usuario_nao_provisionado_recebe_403_generico(ctx: tuple[Any, ...]) -> None:
    client, _, _ = ctx
    resp = await client.get("/provas", headers=_auth(str(uuid.uuid4()), "studio", True))
    assert resp.status_code == 403
    assert resp.json()["error"]["message"] == "Acesso negado."


# ---------------------------------------------------------------------------
# Sem N+1 (RNF-022): nº de SELECTs em provas e de chamadas ao projetor constante
# ---------------------------------------------------------------------------
async def test_listagem_nao_tem_n_mais_1(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    sqls: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _coletar(conn: Any, cursor: Any, statement: str, *_a: Any) -> None:
        sqls.append(statement.lower())

    sqls.clear()
    await _listar(client, _auth(ids["admin"], "studio", True))
    event.remove(engine.sync_engine, "before_cursor_execute", _coletar)

    de_provas = sum(1 for s in sqls if "from provas" in s)
    projetor = sum(1 for s in sqls if "nomes_de_vendedores" in s)
    # 4 provas de 2 vendedores: 2 SELECTs em provas (count + página) e 1 chamada
    # ao projetor de nomes — NÃO escala com o nº de linhas.
    assert de_provas == 2
    assert projetor == 1
