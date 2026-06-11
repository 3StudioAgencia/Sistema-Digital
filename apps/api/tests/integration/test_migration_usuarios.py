"""Migration 0002 (usuarios) contra Postgres REAL (@db) — estrutura e RLS.

O ciclo upgrade→downgrade→upgrade é exercitado pela fixture de sessão
(``usuarios_schema``) somada à validação manual de release; aqui validamos o
RESULTADO: RLS habilitada (postura restritiva — DP-5), CHECK da RN-009 ativo no
banco e unicidade case-insensitive de e-mail.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.db


async def test_rls_habilitada_na_tabela(usuarios_engine: AsyncEngine) -> None:
    async with usuarios_engine.connect() as conn:
        ativo = (
            await conn.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE relname = 'usuarios'")
            )
        ).scalar_one()
    assert ativo is True


async def test_indices_de_filtro_existem(usuarios_engine: AsyncEngine) -> None:
    async with usuarios_engine.connect() as conn:
        nomes = set(
            (
                await conn.execute(
                    text("SELECT indexname FROM pg_indexes WHERE tablename = 'usuarios'")
                )
            ).scalars()
        )
    assert {
        "ix_usuarios_setor",
        "ix_usuarios_ativo",
        "ix_usuarios_nome_lower",
        "ix_usuarios_created_at",
        "uq_usuarios_email_lower",
    } <= nomes


async def test_check_rn009_no_banco(usuarios_engine: AsyncEngine) -> None:
    """Defesa em profundidade: mesmo um INSERT por fora da API respeita a RN-009."""
    async with usuarios_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(
                text(
                    "INSERT INTO usuarios (id, nome, email, setor) "
                    "VALUES (gen_random_uuid(), 'X', 'x@y.z', 'vendedor')"
                )
            )
    async with usuarios_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(
                text(
                    "INSERT INTO usuarios (id, nome, email, setor, localizacao) "
                    "VALUES (gen_random_uuid(), 'X', 'x@y.z', 'clicheria', 'matriz')"
                )
            )


async def test_email_unico_case_insensitive(usuarios_engine: AsyncEngine) -> None:
    async with usuarios_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO usuarios (id, nome, email, setor) "
                "VALUES (gen_random_uuid(), 'A', 'Dup@x.y', 'studio')"
            )
        )
    async with usuarios_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(
                text(
                    "INSERT INTO usuarios (id, nome, email, setor) "
                    "VALUES (gen_random_uuid(), 'B', 'dup@X.Y', 'studio')"
                )
            )
