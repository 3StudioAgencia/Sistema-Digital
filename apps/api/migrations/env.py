"""Ambiente do Alembic — execução ASSÍNCRONA contra a conexão direta (ADR-007).

Lê ``MIGRATIONS_DATABASE_URL`` do ambiente (ou .env local). Deliberadamente NÃO
usa o ``Settings`` completo da aplicação: rodar migrations não deve exigir
``DATABASE_URL`` de runtime nem credenciais de R2.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.infrastructure.config import _coerce_asyncpg_url

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: rodar migrations no mesmo processo da app
    # (ou da suíte de testes) não pode silenciar os loggers já configurados
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Sem tabelas de domínio nesta wave — o metadata chega na Wave 2 (C06).
# Quando existir: from src.adapters.outbound.db.models import metadata
target_metadata = None


class _MigrationSettings(BaseSettings):
    """Só o necessário para migrar — independente do Settings da aplicação."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    migrations_database_url: str


def _database_url() -> str:
    return _coerce_asyncpg_url(_MigrationSettings().migrations_database_url)  # type: ignore[call-arg]


def run_migrations_offline() -> None:
    """Modo offline: emite o SQL sem conectar (``alembic upgrade head --sql``)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    # NullPool: processo de migration abre uma conexão, usa e encerra.
    engine = create_async_engine(_database_url(), poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
