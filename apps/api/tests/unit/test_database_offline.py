"""Camada de banco SEM Postgres: construção do engine, UoW e degradação do ping.

A transação do SQLAlchemy é lazy (só conecta no primeiro SQL), o que permite
validar a semântica do Unit of Work offline. O caminho com banco real está em
tests/integration/test_database.py (@db).
"""

import contextlib

from sqlalchemy.pool import NullPool
from src.infrastructure.config import Settings
from src.infrastructure.database import (
    SqlAlchemyUnitOfWork,
    create_runtime_engine,
    create_session_factory,
    get_session,
    ping,
)

# Porta 9 (discard): conexão recusada imediatamente, sem DNS nem timeout longo
URL_INALCANCAVEL = "postgresql+asyncpg://nouser:nopass@127.0.0.1:9/nada"


def _settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=URL_INALCANCAVEL,
        migrations_database_url=URL_INALCANCAVEL,
    )


class TestEngineDeRuntime:
    def test_usa_nullpool_conforme_adr_007(self) -> None:
        engine = create_runtime_engine(_settings())
        assert isinstance(engine.pool, NullPool)

    async def test_ping_degrada_para_false_com_banco_inacessivel(self) -> None:
        engine = create_runtime_engine(_settings())
        try:
            assert await ping(engine) is False
        finally:
            await engine.dispose()


class TestUnitOfWorkOffline:
    async def test_begin_commit_e_rollback_sem_sql_nao_conectam(self) -> None:
        engine = create_runtime_engine(_settings())
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                uow = SqlAlchemyUnitOfWork(session)
                async with uow:
                    await uow.begin()
                    assert session.in_transaction()
                    assert uow.session is session
                    await uow.commit()
                assert not session.in_transaction()
        finally:
            await engine.dispose()

    async def test_sair_do_bloco_sem_commit_faz_rollback(self) -> None:
        engine = create_runtime_engine(_settings())
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                uow = SqlAlchemyUnitOfWork(session)
                async with uow:
                    await uow.begin()
                    # begin duplo é no-op seguro (não levanta)
                    await uow.begin()
                assert not session.in_transaction()
        finally:
            await engine.dispose()


class TestGetSession:
    async def test_gerador_entrega_e_fecha_sessao(self) -> None:
        engine = create_runtime_engine(_settings())
        factory = create_session_factory(engine)
        try:
            agen = get_session(factory)
            session = await anext(agen)
            assert session.is_active
            with contextlib.suppress(StopAsyncIteration):
                await anext(agen)
        finally:
            await engine.dispose()
