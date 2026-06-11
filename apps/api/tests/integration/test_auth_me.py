"""Endpoint ``GET /auth/me`` (W1-C03) — prova ponta-a-ponta da verificação de JWT.

Roda OFFLINE: o client recebe um ``JwtVerifier`` de teste com segredo HS256
conhecido (sem rede, sem JWKS real). Cobre token válido (200 + identidade) e os
casos 401 (sem header, malformado, expirado, audience errada) com mensagem
genérica e correlação por request_id.
"""

import datetime as dt
from typing import Any

import jwt
import pytest
from src.adapters.inbound.http.auth import JwtVerifier
from src.infrastructure.config import Settings

from tests.conftest import FakeStorage, make_client, ping_ok

HS256_SECRET = "segredo-integracao-nunca-em-producao"
SUB = "22222222-2222-2222-2222-222222222222"
EMAIL = "studio@3studio.test"


def _token(**overrides: Any) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": SUB,
        "email": EMAIL,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    claims.update(overrides)
    return jwt.encode(claims, HS256_SECRET, algorithm="HS256")


@pytest.fixture
async def auth_client(settings: Settings, fake_storage: FakeStorage) -> Any:
    verifier = JwtVerifier(hs256_secret=HS256_SECRET)
    async with make_client(settings, fake_storage, ping_ok, jwt_verifier=verifier) as c:
        yield c


async def test_me_token_valido(auth_client: Any) -> None:
    resp = await auth_client.get("/auth/me", headers={"Authorization": f"Bearer {_token()}"})
    assert resp.status_code == 200
    assert resp.json() == {"sub": SUB, "email": EMAIL, "role": "authenticated"}


async def test_me_sem_authorization(auth_client: Any) -> None:
    resp = await auth_client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"
    body = resp.json()
    assert body["error"]["code"] == "http_error"
    # Correlação preservada mesmo no 401 (RNF-024).
    assert body["error"]["request_id"]


async def test_me_token_malformado(auth_client: Any) -> None:
    resp = await auth_client.get("/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert resp.status_code == 401


async def test_me_token_expirado(auth_client: Any) -> None:
    past = dt.datetime.now(tz=dt.UTC) - dt.timedelta(hours=1)
    resp = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {_token(exp=past)}"}
    )
    assert resp.status_code == 401


async def test_me_audience_incorreta(auth_client: Any) -> None:
    resp = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {_token(aud='anon')}"}
    )
    assert resp.status_code == 401


async def test_me_mensagem_generica(auth_client: Any) -> None:
    # Anti-enumeração: a mensagem não revela QUAL parte falhou.
    resp = await auth_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {_token(aud='anon')}"}
    )
    msg = resp.json()["error"]["message"].lower()
    assert "aud" not in msg
    assert "expir" not in msg
    assert "signature" not in msg and "assinatura" not in msg
