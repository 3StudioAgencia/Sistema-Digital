"""Camada de banco SEM Postgres: construção do engine, UoW e degradação do ping.

A transação do SQLAlchemy é lazy (só conecta no primeiro SQL), o que permite
validar a semântica do Unit of Work offline. O caminho com banco real está em
tests/integration/test_database.py (@db).
"""

import contextlib
import logging

import pytest
from sqlalchemy.pool import NullPool
from src.adapters.outbound.db.unit_of_work import SqlAlchemyUnitOfWork
from src.infrastructure.config import Settings
from src.infrastructure.database import (
    RoleDeRuntimePrivilegiadoError,
    _exigir_role_runtime_nao_privilegiado,
    create_runtime_engine,
    create_session_factory,
    get_session,
    ping,
    verificar_role_runtime_nao_privilegiado,
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

    async def test_ping_falho_loga_warning_com_error_type_sem_vazar(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """W0-A-003: o readiness 'down' deixa rastro diagnóstico (RNF-024) —
        tipo da exceção, nunca a connection string."""
        engine = create_runtime_engine(_settings())
        try:
            with caplog.at_level(logging.WARNING, logger="rastreio.database"):
                assert await ping(engine) is False
        finally:
            await engine.dispose()

        avisos = [r for r in caplog.records if r.name == "rastreio.database"]
        assert avisos, "esperava um WARNING diagnóstico do ping falho"
        assert getattr(avisos[0], "error_type", None)  # tipo da exceção presente
        assert "nopass" not in caplog.text  # credencial NÃO vaza no log


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


class TestChecagemDeRolePrivilegiado:
    """M-01 (remediação W3): o gate de role só vale em staging/produção e recusa um
    role de conexão superuser/``BYPASSRLS`` (que ignoraria a RLS)."""

    @pytest.mark.parametrize("app_env", ["staging", "production"])
    @pytest.mark.parametrize(("is_super", "bypass"), [(True, False), (False, True), (True, True)])
    def test_levanta_em_deploy_com_role_privilegiado(
        self, app_env: str, is_super: bool, bypass: bool
    ) -> None:
        with pytest.raises(RoleDeRuntimePrivilegiadoError):
            _exigir_role_runtime_nao_privilegiado(
                app_env=app_env, role="postgres", is_superuser=is_super, bypassrls=bypass
            )

    @pytest.mark.parametrize("app_env", ["staging", "production"])
    def test_passa_em_deploy_com_role_nao_owner(self, app_env: str) -> None:
        # role NOBYPASSRLS não-owner (ex.: rastreio_runtime) sobe normalmente.
        _exigir_role_runtime_nao_privilegiado(
            app_env=app_env, role="rastreio_runtime", is_superuser=False, bypassrls=False
        )

    @pytest.mark.parametrize("app_env", ["dev", "test"])
    def test_nao_checa_fora_de_deploy_mesmo_privilegiado(self, app_env: str) -> None:
        # dev/test conectam como owner (`postgres`) de PROPÓSITO — gate não dispara.
        _exigir_role_runtime_nao_privilegiado(
            app_env=app_env, role="postgres", is_superuser=True, bypassrls=True
        )

    async def test_verificador_degrada_quando_banco_inacessivel_no_boot(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Banco fora do ar no boot em produção: a app NÃO derruba — loga e segue
        (filosofia W0-C01). O gate só levanta quando o banco responde."""
        engine = create_runtime_engine(
            Settings(
                _env_file=None,  # type: ignore[call-arg]
                app_env="production",
                database_url=URL_INALCANCAVEL,
                migrations_database_url=URL_INALCANCAVEL,
            )
        )
        try:
            with caplog.at_level(logging.WARNING, logger="rastreio.database"):
                await verificar_role_runtime_nao_privilegiado(engine, "production")
        finally:
            await engine.dispose()
        assert any(
            getattr(r, "event", None) == "runtime_role_check_skipped" for r in caplog.records
        )
        assert "nopass" not in caplog.text  # connection string não vaza no log


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
