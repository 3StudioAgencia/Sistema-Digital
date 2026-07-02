"""Fixtures dos testes de integração com Postgres real (@db) — W1-C04.

``usuarios_schema`` aplica as migrations (``alembic upgrade head``) UMA vez por
sessão no banco de teste; cada teste trunca ``usuarios`` para isolamento.
"""

import os
from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def usuarios_schema(database_url: str) -> str:
    """Banco de teste com as migrations aplicadas até head. Devolve a URL.

    Roda como fixture SÍNCRONA de sessão: o ``env.py`` do Alembic usa
    ``asyncio.run`` internamente, o que exige não haver event loop corrente.
    """
    anterior = os.environ.get("MIGRATIONS_DATABASE_URL")
    os.environ["MIGRATIONS_DATABASE_URL"] = database_url
    try:
        config = AlembicConfig("alembic.ini")
        command.upgrade(config, "head")
    finally:
        if anterior is None:
            os.environ.pop("MIGRATIONS_DATABASE_URL", None)
        else:
            os.environ["MIGRATIONS_DATABASE_URL"] = anterior
    return database_url


@pytest.fixture
async def usuarios_engine(usuarios_schema: str) -> AsyncIterator[AsyncEngine]:
    """Engine por teste (loop é por função no pytest-asyncio) + tabelas limpas.

    ``provas`` entra no TRUNCATE junto (W2-C06): a FK ``provas.vendedor_id``
    impediria truncar ``usuarios`` isoladamente. ``movimentacoes`` (W3-C11) e
    ``assinaturas`` (W3-C12) entram junto: as FKs ``movimentacoes.prova_id``,
    ``movimentacoes.assinatura_ref`` e ``assinaturas.prova_id`` impediriam truncar
    ``provas``/``assinaturas`` isoladamente. ``system_settings`` (W2-C09) e
    ``rate_limit_contadores`` (W3-C10) entram no mesmo TRUNCATE para isolar os
    testes de configuração e de rate limiting (sem FK — independentes).
    """
    engine = create_async_engine(usuarios_schema, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE audit_log, movimentacoes, assinaturas, provas, usuarios, "
                "system_settings, rate_limit_contadores, auth_credentials, auth_sessions"
            )
        )
    try:
        yield engine
    finally:
        await engine.dispose()
