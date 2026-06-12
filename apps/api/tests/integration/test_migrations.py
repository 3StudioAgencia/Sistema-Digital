"""Ciclo completo do Alembic em ambiente limpo (critério de aceitação §5.1).

``upgrade head`` cria a baseline (pgcrypto); ``downgrade base`` desfaz; novo
``upgrade head`` comprova repetibilidade. Testes SÍNCRONOS de propósito: o
env.py do Alembic chama ``asyncio.run`` e não pode rodar dentro de um loop.
"""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.db

API_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_cfg(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    # Env var tem precedência sobre o .env local do desenvolvedor
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", database_url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    return cfg


def _scalar(database_url: str, sql: str) -> object:
    async def _run() -> object:
        engine = create_async_engine(database_url, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text(sql))).scalar()
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def _pgcrypto_instalada(database_url: str) -> bool:
    return bool(
        _scalar(database_url, "SELECT count(*) FROM pg_extension WHERE extname = 'pgcrypto'")
    )


def test_upgrade_e_downgrade_em_ambiente_limpo(alembic_cfg: Config, database_url: str) -> None:
    # Garante ambiente limpo mesmo se uma execução anterior falhou no meio
    command.downgrade(alembic_cfg, "base")

    command.upgrade(alembic_cfg, "head")
    assert _pgcrypto_instalada(database_url), "baseline deve habilitar pgcrypto"
    assert _scalar(database_url, "SELECT version_num FROM alembic_version") == "0003", (
        "head deve registrar a revisão 0003 (lockdown alembic_version — W1-C04)"
    )
    assert _scalar(
        database_url, "SELECT count(*) FROM pg_class WHERE relname = 'usuarios'"
    ) == 1, "0002 deve criar a tabela usuarios"

    command.downgrade(alembic_cfg, "base")
    assert not _pgcrypto_instalada(database_url), "downgrade deve remover a extensão"
    assert _scalar(database_url, "SELECT count(*) FROM alembic_version") == 0, (
        "base deve zerar o histórico de revisões"
    )
    assert _scalar(
        database_url, "SELECT count(*) FROM pg_class WHERE relname = 'usuarios'"
    ) == 0, "downgrade da 0002 deve remover a tabela usuarios"
    assert _scalar(
        database_url,
        "SELECT count(*) FROM pg_type WHERE typname IN ('setor_enum', 'localizacao_enum')",
    ) == 0, "downgrade da 0002 deve remover os enums de domínio"

    # Repetibilidade: aplicar de novo após downgrade funciona (e deixa o banco pronto)
    command.upgrade(alembic_cfg, "head")
    assert _pgcrypto_instalada(database_url)


def test_downgrade_em_producao_preserva_extensao_compartilhada(
    alembic_cfg: Config, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W0-A-014: em ambiente gerenciado (staging/produção) o downgrade NÃO dropa
    pgcrypto (extensão compartilhada do Supabase) — só desfaz o registro da
    revisão. O ciclo de dev/test (teste acima) continua removendo a extensão."""
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    assert _pgcrypto_instalada(database_url)

    monkeypatch.setenv("APP_ENV", "production")
    command.downgrade(alembic_cfg, "base")

    assert _pgcrypto_instalada(database_url), "produção: extensão compartilhada preservada"
    assert _scalar(database_url, "SELECT count(*) FROM alembic_version") == 0, (
        "o registro da revisão é desfeito mesmo sem dropar a extensão"
    )

    # Deixa o banco no estado limpo esperado pelos demais testes
    command.upgrade(alembic_cfg, "head")
