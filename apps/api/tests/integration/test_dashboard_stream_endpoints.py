"""GET /dashboard/stream (etapa 3 — realtime SSE) contra Postgres REAL (@db).

Valida o HANDSHAKE do stream como em produção: exige auth (cookie/Bearer via
``get_current_user``), autoriza ``Recurso.DASHBOARD`` (universal — só exige usuário
ativo) numa sessão RLS CURTA e responde ``text/event-stream`` com
``X-Accel-Buffering: no``. Usa um token de ``exp`` CURTO (< margem) para o gerador
ENCERRAR sozinho (``event: expira``) — o teste nunca trava. A entrega do sinal em
si é coberta pelo gerador (unit) e pelo ``pg_notify`` (``test_realtime_notify``).
"""

import datetime as dt
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from src.adapters.inbound.http.auth import JwtVerifier
from src.infrastructure.config import Settings
from src.infrastructure.database import create_request_session_factory

from tests.conftest import FakeStorage, make_client, ping_ok

pytestmark = pytest.mark.db

HS256_SECRET = "segredo-integracao-nunca-em-producao"


def _token(sub: str, setor: str, *, segundos_ate_expirar: int) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": sub,
        "user_id": sub,
        "email": "x@y.z",
        "setor": setor,
        "administrador": False,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(seconds=segundos_ate_expirar),
    }
    return jwt.encode(claims, HS256_SECRET, algorithm="HS256")


@pytest.fixture
async def stream_ctx(
    settings: Settings, database_url: str
) -> AsyncIterator[tuple[httpx.AsyncClient, str]]:
    engine = create_async_engine(database_url, poolclass=NullPool)
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, :nome, :email, 'studio', NULL, false)"
            ),
            {"id": uid, "nome": "Studio SSE", "email": f"{uid}@x.z"},
        )
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    try:
        async with client as c:
            yield c, uid
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": uid})
        await engine.dispose()


async def test_stream_sem_auth_e_401(stream_ctx: tuple[httpx.AsyncClient, str]) -> None:
    client, _ = stream_ctx
    resp = await client.get("/dashboard/stream")
    assert resp.status_code == 401


async def test_stream_autenticado_abre_event_stream_e_encerra(
    stream_ctx: tuple[httpx.AsyncClient, str],
) -> None:
    client, uid = stream_ctx
    # exp curto (< margem de 60s) → o gerador manda "expira" e ENCERRA sozinho.
    token = _token(uid, "studio", segundos_ate_expirar=30)
    async with client.stream(
        "GET", "/dashboard/stream", headers={"Authorization": f"Bearer {token}"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers.get("x-accel-buffering") == "no"
        assert resp.headers.get("cache-control") == "no-store"
        corpo = "".join([chunk async for chunk in resp.aiter_text()])
    assert "event: conectado" in corpo
    assert "event: expira" in corpo
