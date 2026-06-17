"""GET /provas — filtro multi-status + ``atrasada`` (W4-C16/DP-6) contra Postgres (@db).

O Dashboard liga os cards à listagem (C07): "Com Vendedor" deep-linka MÚLTIPLOS
status (``?status=a&status=b``) e "Atrasadas" liga ``?atrasada=true``. Estes testes
travam as duas extensões SEM regredir o C07 (a regra de atraso é a MESMA do
Dashboard — ``private.instante_limite_atraso``).
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


def _auth(sub: str, setor: str, admin: bool = False) -> dict[str, str]:
    now = dt.datetime.now(tz=dt.UTC)
    token = jwt.encode(
        {
            "sub": sub,
            "user_id": sub,
            "setor": setor,
            "administrador": admin,
            "role": "authenticated",
            "aud": "authenticated",
            "iat": now,
            "exp": now + dt.timedelta(hours=1),
        },
        HS256_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_usuario(engine: AsyncEngine, *, setor: str, nome: str, admin: bool = False) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, :nome, :email, :setor, :loc, :adm)"
            ),
            {"id": uid, "nome": nome, "email": f"{uid}@x.z", "setor": setor, "loc": loc, "adm": admin},
        )
    return uid


async def _seed_prova(
    engine: AsyncEngine, *, vendedor_id: str, status: str, created_at: dt.datetime | None = None
) -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type, created_at) "
                "VALUES (:id, :codigo, 'Etiqueta', '155295', 'Cafe', :v, 'matriz', :status, "
                "'provas/x/arte.png', 'image/png', COALESCE(:created_at, now()))"
            ),
            {"id": uid, "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)), "v": vendedor_id,
             "status": status, "created_at": created_at},
        )
    return uid


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, dict[str, str]]]:
    engine = usuarios_engine
    admin = await _seed_usuario(engine, setor="studio", nome="Monica", admin=True)
    v = await _seed_usuario(engine, setor="vendedor", nome="Regiane")
    velho = dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=30)
    ids = {
        "admin": admin,
        # multi-status: duas posses distintas do vendedor
        "retirada_velha": await _seed_prova(engine, vendedor_id=v, status="retirada_vendedor", created_at=velho),
        "encaminhada_nova": await _seed_prova(engine, vendedor_id=v, status="encaminhada_para_vendedor"),
        # atrasada: ativa e velha; terminal velha NÃO atrasa; ativa nova NÃO atrasa
        "aprovada_velha": await _seed_prova(engine, vendedor_id=v, status="aprovada_vendedor", created_at=velho),
        "terminal_velha": await _seed_prova(engine, vendedor_id=v, status="recebida_clicheria", created_at=velho),
        "criada_nova": await _seed_prova(engine, vendedor_id=v, status="criada"),
    }
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, ids


async def _ids(client: httpx.AsyncClient, params: list[tuple[str, str]], admin: str) -> set[str]:
    resp = await client.get("/provas", params=params, headers=_auth(admin, "studio", True))
    assert resp.status_code == 200, resp.text
    return {i["id"] for i in resp.json()["items"]}


async def test_filtro_status_multiplo_é_um_ou_outro(ctx: tuple[Any, ...]) -> None:
    client, ids = ctx
    achados = await _ids(
        client,
        [("status", "retirada_vendedor"), ("status", "encaminhada_para_vendedor")],
        ids["admin"],
    )
    assert achados == {ids["retirada_velha"], ids["encaminhada_nova"]}


async def test_filtro_status_unico_continua_funcionando(ctx: tuple[Any, ...]) -> None:
    client, ids = ctx
    achados = await _ids(client, [("status", "aprovada_vendedor")], ids["admin"])
    assert achados == {ids["aprovada_velha"]}


async def test_filtro_atrasada_so_ativas_e_velhas(ctx: tuple[Any, ...]) -> None:
    """atrasada=true: retirada_velha + aprovada_velha (ativas, paradas além do
    limiar). A terminal velha e as ativas novas NÃO entram."""
    client, ids = ctx
    achados = await _ids(client, [("atrasada", "true")], ids["admin"])
    assert achados == {ids["retirada_velha"], ids["aprovada_velha"]}


async def test_atrasada_combina_com_status(ctx: tuple[Any, ...]) -> None:
    """Clique numa linha de vendedor do card Atrasadas combina os filtros."""
    client, ids = ctx
    achados = await _ids(
        client, [("atrasada", "true"), ("status", "aprovada_vendedor")], ids["admin"]
    )
    assert achados == {ids["aprovada_velha"]}
