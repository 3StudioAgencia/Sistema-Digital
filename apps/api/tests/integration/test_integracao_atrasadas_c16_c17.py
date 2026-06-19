"""Integração C16 ↔ C17 (@db) — o número compartilhado "Atrasadas" bate nos DOIS lados.

Guardrail da remediação da Wave 5 (prompt §0.2/§3 cuidado A, critério de GO §6.2):
Dashboard (C16) e Relatórios (C17) **dividem** o mesmo código de atraso
(``atraso_sql.SQL_PREDICADO_ATRASADA`` / ``SQL_ULTIMO_EVENTO`` + a função
``private.instante_limite_atraso`` + o delay de ``system_settings``). Uma correção
nesse código compartilhado precisa manter os DOIS lados corretos — este teste
prova, na MESMA fixture, que ``GET /dashboard`` (``atrasadas_total``),
``GET /relatorios/geral`` (``len(provas_atrasadas)``) e ``GET /relatorios/vendedores``
(``atrasadas_total``) devolvem o MESMO número. Se um lado quebrar sem o outro, falha.
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
) -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type, created_at) "
                "VALUES (:id, :codigo, 'Ricota fresca', '150150', 'Laticinios Artvac', :vendedor, "
                ":rota, :status, 'provas/x/arte.png', 'image/png', COALESCE(:created_at, now()))"
            ),
            {
                "id": uid,
                "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)),
                "vendedor": vendedor_id,
                "rota": rota,
                "status": status,
                "created_at": created_at,
            },
        )
    return uid


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, dict[str, str]]]:
    engine = usuarios_engine
    admin = await _seed_usuario(engine, setor="studio", nome="Monica", admin=True)
    v1 = await _seed_usuario(engine, setor="vendedor", nome="Regiane", loc="filial")
    v2 = await _seed_usuario(engine, setor="vendedor", nome="Packon", loc="matriz")

    velho = dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=30)  # além do delay (48h úteis)

    # 2 ATRASADAS: ativas (posse do vendedor), paradas há 30 dias, sem movimentação.
    await _seed_prova(engine, vendedor_id=v1, status="retirada_vendedor", created_at=velho)
    await _seed_prova(
        engine, vendedor_id=v2, status="encaminhada_para_vendedor", rota="filial", created_at=velho
    )
    # NÃO atrasada: ativa, mas recém-criada (dentro do limiar).
    await _seed_prova(engine, vendedor_id=v1, status="criada")
    # NÃO atrasada: VELHA mas TERMINAL (recebida_clicheria é excluída do predicado).
    await _seed_prova(
        engine, vendedor_id=v2, status="recebida_clicheria", rota="lam_matriz", created_at=velho
    )
    # NÃO atrasada: VELHA mas TERMINAL (cancelada também é excluída).
    await _seed_prova(engine, vendedor_id=v1, status="cancelada", created_at=velho)

    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, {"admin": admin, "v1": v1, "v2": v2}


async def test_atrasadas_bate_no_dashboard_e_no_relatorio(ctx: tuple[Any, ...]) -> None:
    """O MESMO número de "Atrasadas" sai do C16 (dashboard) e do C17 (relatórios)."""
    client, ids = ctx
    auth = _auth(ids["admin"], "studio", True)

    dash = (await client.get("/dashboard", headers=auth)).json()
    geral = (await client.get("/relatorios/geral", headers=auth)).json()
    vendedores = (await client.get("/relatorios/vendedores", headers=auth)).json()

    esperado = 2  # recomputado à mão: as 2 ativas-velhas; terminais e a recém-criada NÃO contam
    assert dash["atrasadas_total"] == esperado
    # Os DOIS lados batem entre si (consistência por construção — mesmo predicado/função/delay).
    assert len(geral["provas_atrasadas"]) == dash["atrasadas_total"]
    assert vendedores["atrasadas_total"] == dash["atrasadas_total"]
    # E o breakdown por vendedor do dashboard soma o mesmo total.
    assert sum(a["total"] for a in dash["atrasadas_por_vendedor"]) == esperado
