"""Captura de eventos no ``audit_log`` (W6-C20) contra Postgres REAL (@db).

Prova que a captura é efeito colateral ATÔMICO dos casos de uso, sem mudar a regra
deles, e que a reprovação/cancelamento/reinício/travessias ficam todos visíveis
(RNF-006). Conta as linhas como OWNER (bypass RLS) — o foco aqui é o que foi
GRAVADO, não quem lê (isso é o teste de RLS/endpoints).
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


async def _seed_prova(
    engine: AsyncEngine, *, vendedor_id: str, status: str = "criada", rota: str = "matriz"
) -> tuple[str, str]:
    uid = str(uuid.uuid4())
    codigo = gerar_codigo(dt.datetime.now(tz=dt.UTC))
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO provas (id, codigo, nome, requerimento, cliente, vendedor_id, rota, "
                "status, arte_key, arte_content_type) VALUES (:id, :codigo, 'P', '155', 'C', "
                ":vendedor, :rota, :status, 'provas/x/arte.png', 'image/png')"
            ),
            {"id": uid, "codigo": codigo, "vendedor": vendedor_id, "rota": rota, "status": status},
        )
    return uid, codigo


async def _eventos(engine: AsyncEngine, *, prova_id: str | None = None) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        if prova_id is not None:
            stmt = text(
                "SELECT evento, ator_id::text AS ator_id, motivo, acao FROM audit_log "
                "WHERE prova_id = :p ORDER BY seq"
            )
            rows = (await conn.execute(stmt, {"p": prova_id})).all()
        else:
            stmt = text(
                "SELECT evento, ator_id::text AS ator_id, motivo, acao FROM audit_log ORDER BY seq"
            )
            rows = (await conn.execute(stmt)).all()
    return [
        {"evento": r.evento, "ator_id": r.ator_id, "motivo": r.motivo, "acao": r.acao}
        for r in rows
    ]


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


async def test_criacao_grava_criou_prova(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    resp = await client.post(
        "/provas",
        data={
            "nome": "Etiqueta",
            "requerimento": "155295",
            "cliente": "Cafe",
            "vendedor_id": ids["vendedor"],
            "rota": "matriz",
        },
        files={"arte": ("a.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 16, "image/jpeg")},
        headers=_auth(ids["admin"], "studio", True),
    )
    assert resp.status_code == 201, resp.text
    eventos = await _eventos(engine, prova_id=resp.json()["id"])
    assert [e["evento"] for e in eventos] == ["criou_prova"]
    assert eventos[0]["ator_id"] == ids["admin"]


async def test_escaneamento_grava_escaneou_qr(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova_id, codigo = await _seed_prova(engine, vendedor_id=ids["vendedor"])
    resp = await client.post(
        "/provas/identificar", json={"codigo": codigo}, headers=_auth(ids["vendedor"], "vendedor")
    )
    assert resp.status_code == 200, resp.text
    eventos = await _eventos(engine, prova_id=prova_id)
    assert [e["evento"] for e in eventos] == ["escaneou_qr"]
    assert eventos[0]["ator_id"] == ids["vendedor"]


async def test_escaneamento_404_nao_loga(ctx: tuple[Any, ...]) -> None:
    """Anti-enumeração: código inexistente → 404 e NENHUM evento (não vaza)."""
    client, engine, ids = ctx
    resp = await client.post(
        "/provas/identificar",
        json={"codigo": "PRV-2026-06-ZZZZZZ"},
        headers=_auth(ids["vendedor"], "vendedor"),
    )
    assert resp.status_code == 404
    assert await _eventos(engine) == []


async def test_reprovacao_grava_evento_com_motivo(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova_id, _ = await _seed_prova(engine, vendedor_id=ids["vendedor"], status="retirada_vendedor")
    resp = await client.post(
        f"/provas/{prova_id}/transicoes",
        json={
            "acao": "reprovar",
            "assinatura": ASSINATURA,
            "idempotency_key": str(uuid.uuid4()),
            "motivo": "cor errada",
        },
        headers=_auth(ids["vendedor"], "vendedor"),
    )
    assert resp.status_code == 200, resp.text
    eventos = await _eventos(engine, prova_id=prova_id)
    assert [e["evento"] for e in eventos] == ["reprovou_prova"]
    assert eventos[0]["motivo"] == "cor errada"
    assert eventos[0]["acao"] == "reprovar"


async def test_cancelamento_grava_cancelou_prova(ctx: tuple[Any, ...]) -> None:
    client, engine, ids = ctx
    prova_id, _ = await _seed_prova(engine, vendedor_id=ids["vendedor"], status="criada")
    resp = await client.post(
        f"/provas/{prova_id}/cancelar",
        json={"motivo": "duplicada", "idempotency_key": str(uuid.uuid4())},
        headers=_auth(ids["admin"], "studio", True),
    )
    assert resp.status_code == 200, resp.text
    eventos = await _eventos(engine, prova_id=prova_id)
    assert [e["evento"] for e in eventos] == ["cancelou_prova"]
    assert eventos[0]["motivo"] == "duplicada"


async def test_transicao_idempotente_nao_duplica_evento(ctx: tuple[Any, ...]) -> None:
    """Reenvio com a MESMA idempotency_key converge (200) e NÃO cria 2º evento."""
    client, engine, ids = ctx
    prova_id, _ = await _seed_prova(engine, vendedor_id=ids["vendedor"], status="criada")
    chave = str(uuid.uuid4())
    body = {"acao": "identificar_e_assinar", "assinatura": ASSINATURA, "idempotency_key": chave}
    r1 = await client.post(
        f"/provas/{prova_id}/transicoes", json=body, headers=_auth(ids["vendedor"], "vendedor")
    )
    r2 = await client.post(
        f"/provas/{prova_id}/transicoes", json=body, headers=_auth(ids["vendedor"], "vendedor")
    )
    assert r1.status_code == 200 and r2.status_code == 200
    eventos = await _eventos(engine, prova_id=prova_id)
    assert [e["evento"] for e in eventos] == ["mudou_status"]  # UMA linha, não duas
