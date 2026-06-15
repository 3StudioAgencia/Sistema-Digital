"""Detalhe/arte/etiqueta de UMA prova (W2-C08) contra Postgres REAL (@db).

Exercita o caminho HTTP inteiro como em produção (``SET LOCAL ROLE authenticated``
+ claims propagados — ADR-008/ADR-034), validando os critérios de aceitação §6:

- página UNIVERSAL escopada pela RLS (Matriz §7): 3Studio/Clicheria/Admin todas,
  Vendedor as suas, Motorista as "Em Trânsito";
- ANTI-VAZAMENTO (§11): prova inexistente e prova fora do escopo retornam o MESMO
  404 genérico (mensagem idêntica) — sem revelar se a prova existe;
- ``ciclo_atual`` e ``vendedor_nome`` (DP-1/DP-7) no detalhe, resolvendo o nome até
  para 3Studio NÃO-admin / Motorista;
- PROXY da arte (DP-5): bytes + content-type do R2 (mockado), escopado, sem URL
  pública nem exposição da key;
- ETIQUETA universal-em-escopo (DP-8): o vendedor dono imprime; fora do escopo → 404.
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
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


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
            {
                "id": uid,
                "nome": nome,
                "email": f"{uid}@x.z",
                "setor": setor,
                "loc": loc,
                "adm": administrador,
            },
        )
    return uid


async def _seed_prova(
    engine: AsyncEngine,
    storage: FakeStorage,
    *,
    vendedor_id: str,
    status: str = "criada",
    rota: str = "matriz",
    nome: str = "Mussarela fatiada",
    requerimento: str = "123456",
    cliente: str = "Edulat",
) -> str:
    """Insere a prova E carrega a arte no storage mockado sob a key derivada do id."""
    uid = str(uuid.uuid4())
    arte_key = f"provas/{uid}/arte.png"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type) "
                "VALUES (:id, :codigo, :nome, :req, :cliente, :vendedor, :rota, :status, "
                ":arte_key, 'image/png')"
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
                "arte_key": arte_key,
            },
        )
    storage.upload(arte_key, PNG_BYTES, "image/png")
    return uid


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, FakeStorage, dict[str, Any]]]:
    engine = usuarios_engine
    storage = FakeStorage()
    admin = await _seed_usuario(engine, setor="studio", nome="Monica", administrador=True)
    studio = await _seed_usuario(engine, setor="studio", nome="Studio Op")  # NÃO-admin (DP-7)
    motorista = await _seed_usuario(engine, setor="motorista", nome="Moto Op")
    regiane = await _seed_usuario(engine, setor="vendedor", nome="Regiane")
    packon = await _seed_usuario(engine, setor="vendedor", nome="Packon")

    p_criada_reg = await _seed_prova(engine, storage, vendedor_id=regiane)
    p_transito_reg = await _seed_prova(
        engine,
        storage,
        vendedor_id=regiane,
        status="com_motorista_ida_laminacao",
        rota="lam_matriz",
    )
    p_criada_pack = await _seed_prova(engine, storage, vendedor_id=packon, cliente="Cocatrel")

    ids = {
        "admin": admin,
        "studio": studio,
        "motorista": motorista,
        "regiane": regiane,
        "packon": packon,
        "p_criada_reg": p_criada_reg,
        "p_transito_reg": p_transito_reg,
        "p_criada_pack": p_criada_pack,
    }
    client = make_client(
        settings,
        storage,
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, engine, storage, ids


# ---------------------------------------------------------------------------
# Detalhe (GET /provas/{id}) — escopo, campos, anti-vazamento
# ---------------------------------------------------------------------------
async def test_admin_ve_detalhe_com_todos_os_campos(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_criada_reg']}", headers=_auth(ids["admin"], "studio", True)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == ids["p_criada_reg"]
    assert body["nome"] == "Mussarela fatiada"
    assert body["cliente"] == "Edulat"
    assert body["vendedor_nome"] == "Regiane"  # DP-7
    assert body["rota"] == "matriz"
    assert body["status"] == "criada"
    assert body["ciclo_atual"] == 1  # DP-1: nasce 1
    assert body["created_at"] is not None
    assert body["finalizada_em"] is None  # populado só pelo C11


async def test_studio_nao_admin_resolve_nome_do_vendedor(ctx: tuple[Any, ...]) -> None:
    """DP-7: a RLS de usuarios bloquearia o nome num JOIN; o projetor resolve."""
    client, _, _, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_criada_pack']}", headers=_auth(ids["studio"], "studio")
    )
    assert resp.status_code == 200
    assert resp.json()["vendedor_nome"] == "Packon"


async def test_vendedor_ve_detalhe_da_propria(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_criada_reg']}", headers=_auth(ids["regiane"], "vendedor")
    )
    assert resp.status_code == 200
    assert resp.json()["vendedor_nome"] == "Regiane"


async def test_motorista_ve_em_transito_mas_nao_criada(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    ok = await client.get(
        f"/provas/{ids['p_transito_reg']}", headers=_auth(ids["motorista"], "motorista")
    )
    assert ok.status_code == 200
    nao = await client.get(
        f"/provas/{ids['p_criada_reg']}", headers=_auth(ids["motorista"], "motorista")
    )
    assert nao.status_code == 404  # "criada" não é "Em Trânsito"


async def test_vendedor_fora_de_escopo_e_inexistente_sao_o_mesmo_404(ctx: tuple[Any, ...]) -> None:
    """Anti-enumeração (§11): a prova de OUTRO vendedor e uma prova inexistente
    devolvem o MESMO status E a MESMA mensagem — Regiane não distingue os casos."""
    client, _, _, ids = ctx
    fora = await client.get(
        f"/provas/{ids['p_criada_pack']}", headers=_auth(ids["regiane"], "vendedor")
    )
    inexistente = await client.get(
        f"/provas/{uuid.uuid4()}", headers=_auth(ids["regiane"], "vendedor")
    )
    assert fora.status_code == inexistente.status_code == 404
    assert fora.json()["error"]["message"] == inexistente.json()["error"]["message"]
    assert fora.json()["error"]["message"] == "Prova não encontrada."


async def test_detalhe_sem_token_e_401(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    resp = await client.get(f"/provas/{ids['p_criada_reg']}")
    assert resp.status_code == 401


async def test_detalhe_usuario_nao_provisionado_e_403(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_criada_reg']}", headers=_auth(str(uuid.uuid4()), "studio", True)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Arte (GET /provas/{id}/arte) — proxy escopado do R2 privado (DP-5)
# ---------------------------------------------------------------------------
async def test_arte_em_escopo_devolve_bytes_e_content_type(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_criada_reg']}/arte", headers=_auth(ids["regiane"], "vendedor")
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.content == PNG_BYTES  # bytes do R2 (mockado), sem URL pública


async def test_arte_fora_de_escopo_e_404_generico(ctx: tuple[Any, ...]) -> None:
    """Mesma resposta de prova inexistente: a prova é resolvida (RLS) antes do R2."""
    client, _, _, ids = ctx
    fora = await client.get(
        f"/provas/{ids['p_criada_pack']}/arte", headers=_auth(ids["regiane"], "vendedor")
    )
    assert fora.status_code == 404
    inexistente = await client.get(
        f"/provas/{uuid.uuid4()}/arte", headers=_auth(ids["regiane"], "vendedor")
    )
    assert inexistente.status_code == 404


# ---------------------------------------------------------------------------
# Etiqueta (GET /provas/{id}/etiqueta.pdf) — universal-em-escopo (DP-8)
# ---------------------------------------------------------------------------
async def test_etiqueta_acessivel_a_qualquer_perfil_em_escopo(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    # vendedor dono
    dono = await client.get(
        f"/provas/{ids['p_criada_reg']}/etiqueta.pdf", headers=_auth(ids["regiane"], "vendedor")
    )
    assert dono.status_code == 200 and dono.content.startswith(b"%PDF")
    # 3Studio não-admin (vê todas)
    studio = await client.get(
        f"/provas/{ids['p_criada_pack']}/etiqueta.pdf", headers=_auth(ids["studio"], "studio")
    )
    assert studio.status_code == 200 and studio.content.startswith(b"%PDF")


async def test_etiqueta_fora_de_escopo_e_404_generico(ctx: tuple[Any, ...]) -> None:
    client, _, _, ids = ctx
    resp = await client.get(
        f"/provas/{ids['p_criada_pack']}/etiqueta.pdf", headers=_auth(ids["regiane"], "vendedor")
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Prova não encontrada."
