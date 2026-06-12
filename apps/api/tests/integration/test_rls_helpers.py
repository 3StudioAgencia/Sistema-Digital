"""Helpers de RLS (W1-C05 / W1-A-021) chamados DIRETAMENTE sob claims, @db.

As policies de ``usuarios`` já exercitam ``app_is_admin``/``app_current_user_id``
indiretamente; faltava cobertura DIRETA de ``app_setor()`` e ``app_current_claims()``
— entregues ao C06 para a RLS de ``provas`` — e do fallback de "objeto vazio /
default-deny" quando não há claims propagados (a base do fail-closed do C06).
"""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytestmark = pytest.mark.db


def _claims(sub: str, setor: str, administrador: bool) -> str:
    return json.dumps(
        {
            "sub": sub,
            "user_id": sub,
            "setor": setor,
            "administrador": administrador,
            "role": "authenticated",
            "aud": "authenticated",
        }
    )


async def _autenticar(conn: AsyncConnection, sub: str, setor: str, admin: bool) -> None:
    """Propaga claims + troca para authenticated na transação corrente (ADR-008)."""
    await conn.execute(
        text("SELECT set_config('request.jwt.claims', :c, true)"),
        {"c": _claims(sub, setor, admin)},
    )
    await conn.execute(text("SET LOCAL ROLE authenticated"))


def _para_dict(valor: Any) -> dict[str, Any]:
    """asyncpg pode devolver jsonb como dict OU como texto JSON — normaliza."""
    return valor if isinstance(valor, dict) else json.loads(valor)


@pytest.mark.parametrize("setor", ["studio", "vendedor", "motorista", "clicheria"])
async def test_app_setor_retorna_o_setor_propagado(
    usuarios_engine: AsyncEngine, setor: str
) -> None:
    sub = str(uuid.uuid4())
    async with usuarios_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, setor, False)
            valor = (await conn.execute(text("SELECT public.app_setor()"))).scalar_one()
            assert valor == setor
        finally:
            await trans.rollback()


async def test_app_current_claims_round_trip(usuarios_engine: AsyncEngine) -> None:
    sub = str(uuid.uuid4())
    async with usuarios_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _autenticar(conn, sub, "vendedor", True)
            bruto = (await conn.execute(text("SELECT public.app_current_claims()"))).scalar_one()
            claims = _para_dict(bruto)
            assert claims["setor"] == "vendedor"
            assert claims["administrador"] is True
            assert claims["user_id"] == sub
            assert claims["role"] == "authenticated"
        finally:
            await trans.rollback()


async def test_helpers_sem_claims_default_deny(usuarios_engine: AsyncEngine) -> None:
    """Sem claims propagados (GUC ausente): app_current_claims() = {} e os
    derivados negam por padrão — base do fail-closed que o C06 herda."""
    async with usuarios_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(text("SET LOCAL ROLE authenticated"))
            claims = _para_dict(
                (await conn.execute(text("SELECT public.app_current_claims()"))).scalar_one()
            )
            assert claims == {}
            assert (await conn.execute(text("SELECT public.app_setor()"))).scalar_one() is None
            assert (await conn.execute(text("SELECT public.app_is_admin()"))).scalar_one() is False
            assert (
                await conn.execute(text("SELECT public.app_current_user_id()"))
            ).scalar_one() is None
        finally:
            await trans.rollback()
