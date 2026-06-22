"""Integridade do chain do ``audit_log`` (W6-C20 / DP-4) contra Postgres REAL (@db).

O log é tamper-EVIDENT: cada linha encadeia o hash da anterior (SHA-256 de
prev_hash || campos). ``private.audit_log_verificar`` recomputa o chain e aponta a
1ª linha divergente. Testes:

- o chain recém-gerado é íntegro (intacto, sem quebra);
- ADULTERAÇÃO: alterar uma linha (mesmo com o trigger desativado, como faria um
  ataque direto ao banco) FAZ a verificação acusar a quebra naquela ``seq``.
"""

import base64
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
ASSINATURA = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16).decode()


def _auth(sub: str, setor: str, admin: bool = False) -> dict[str, str]:
    now = dt.datetime.now(tz=dt.UTC)
    claims: dict[str, Any] = {
        "sub": sub,
        "user_id": sub,
        "setor": setor,
        "administrador": admin,
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
    }
    return {"Authorization": f"Bearer {jwt.encode(claims, HS256_SECRET, algorithm='HS256')}"}


async def _seed_usuario(engine: AsyncEngine, *, setor: str, admin: bool = False) -> str:
    uid = str(uuid.uuid4())
    loc = "matriz" if setor == "vendedor" else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor, localizacao, administrador) "
                "VALUES (:id, 'U', :email, :setor, :loc, :adm)"
            ),
            {"id": uid, "email": f"{uid}@x.z", "setor": setor, "loc": loc, "adm": admin},
        )
    return uid


async def _seed_prova(engine: AsyncEngine, *, vendedor_id: str) -> str:
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type) VALUES (:id, :codigo, 'P', '1', 'C', "
                ":vendedor, 'matriz', 'criada', 'provas/x/arte.png', 'image/png')"
            ),
            {
                "id": uid,
                "codigo": gerar_codigo(dt.datetime.now(tz=dt.UTC)),
                "vendedor": vendedor_id,
            },
        )
    return uid


@pytest.fixture
async def ctx(
    settings: Settings, usuarios_engine: AsyncEngine
) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncEngine, dict[str, str]]]:
    engine = usuarios_engine
    ids = {
        "admin": await _seed_usuario(engine, setor="studio", admin=True),
        "vendedor": await _seed_usuario(engine, setor="vendedor"),
    }
    client = make_client(
        settings,
        FakeStorage(),
        ping_ok,
        jwt_verifier=JwtVerifier(hs256_secret=HS256_SECRET),
        session_factory=create_request_session_factory(engine),
    )
    async with client as c:
        yield c, engine, ids


async def _gerar_tres_eventos(
    client: httpx.AsyncClient, engine: AsyncEngine, ids: dict[str, str]
) -> str:
    """3 transições no fluxo matriz: mudou_status, aprovou_prova, mudou_status (seq 1..3)."""
    prova = await _seed_prova(engine, vendedor_id=ids["vendedor"])
    passos = [
        ("identificar_e_assinar", _auth(ids["vendedor"], "vendedor"), None),
        ("aprovar", _auth(ids["vendedor"], "vendedor"), None),
        ("identificar_e_assinar", _auth(ids["admin"], "studio", True), None),
    ]
    for acao, headers, motivo in passos:
        body = {"acao": acao, "assinatura": ASSINATURA, "idempotency_key": str(uuid.uuid4())}
        if motivo:
            body["motivo"] = motivo
        r = await client.post(f"/provas/{prova}/transicoes", json=body, headers=headers)
        assert r.status_code == 200, r.text
    return prova


async def _verificar(client: httpx.AsyncClient, ids: dict[str, str]) -> dict[str, Any]:
    resp = await client.post(
        "/auditoria/verificar-integridade", headers=_auth(ids["admin"], "studio", True)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_chain_intacto_apos_geracao(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    await _gerar_tres_eventos(client, engine, ids)
    veredito = await _verificar(client, ids)
    assert veredito["intacto"] is True
    assert veredito["total"] == 3
    assert veredito["quebrou_em"] is None


async def test_adulteracao_quebra_o_chain(ctx: tuple[Any, ...]) -> None:
    """Altera a linha seq=2 DESATIVANDO o trigger (como faria um ataque direto ao
    banco) — a verificação recomputa o chain e acusa a quebra exatamente em seq=2."""
    client, engine, ids = ctx
    await _gerar_tres_eventos(client, engine, ids)

    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_log_append_only"))
        await conn.execute(text("UPDATE audit_log SET motivo = 'adulterado' WHERE seq = 2"))
        await conn.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_log_append_only"))

    veredito = await _verificar(client, ids)
    assert veredito["intacto"] is False
    assert veredito["quebrou_em"] == 2
    assert veredito["total"] == 3


async def test_trigger_bloqueia_update_ate_para_o_owner(ctx: tuple[Any, ...]) -> None:
    """Sem desativar o trigger, NEM o owner consegue UPDATE (append-only estrutural)."""
    from sqlalchemy.exc import DBAPIError

    client, engine, ids = ctx
    await _gerar_tres_eventos(client, engine, ids)
    with pytest.raises(DBAPIError):
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE audit_log SET motivo = 'x' WHERE seq = 1"))
