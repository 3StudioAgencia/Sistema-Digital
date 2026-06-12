"""Conectividade async com PostgreSQL real (testes @db — skip se indisponível).

Valida a estratégia do ADR-007 na prática: o engine de runtime (NullPool +
caches de prepared statement desligados) executa contra um Postgres real.
"""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from src.adapters.outbound.db.unit_of_work import SqlAlchemyUnitOfWork
from src.infrastructure.config import Settings
from src.infrastructure.database import (
    create_runtime_engine,
    create_session_factory,
    ping,
)

pytestmark = pytest.mark.db


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=database_url,
        migrations_database_url=database_url,
    )
    engine = create_runtime_engine(settings)
    yield engine
    await engine.dispose()


async def test_ping_executa_select_1_com_sucesso(engine: AsyncEngine) -> None:
    assert await ping(engine) is True


# O caminho de ping com banco inacessível roda OFFLINE e vive em
# tests/unit/test_database_offline.py — não precisa do marker @db (W0-A-026).


async def test_sessao_async_executa_select_1(engine: AsyncEngine) -> None:
    factory = create_session_factory(engine)
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


async def test_unit_of_work_commit_e_rollback(engine: AsyncEngine) -> None:
    factory = create_session_factory(engine)

    async with factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            await uow.begin()
            await uow.session.execute(text("SELECT 1"))
            await uow.commit()

    # Saída do bloco sem commit → rollback silencioso (nunca deixa transação aberta)
    async with factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            await uow.begin()
            await uow.session.execute(text("SELECT 1"))
        assert not session.in_transaction()
