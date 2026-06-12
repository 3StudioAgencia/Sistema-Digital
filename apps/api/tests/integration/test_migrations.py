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
    assert _scalar(database_url, "SELECT version_num FROM alembic_version") == "0008", (
        "head deve registrar a revisão 0008 (RLS de provas + role de runtime — W2-C06)"
    )
    assert _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'usuarios'") == 1, (
        "0002 deve criar a tabela usuarios"
    )
    # W1-C05: hook de claims (0004) e helpers de RLS (0005) presentes no head.
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc WHERE proname = 'custom_access_token_hook'",
        )
        == 1
    ), "0004 deve criar o custom_access_token_hook"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_proc WHERE proname = 'app_is_admin'") == 1
    ), "0005 deve criar os helpers de RLS"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_policies WHERE tablename = 'usuarios'") == 5
    ), "0005 deve criar as 5 policies de usuarios"
    # W1-A-004: a 0006 fixa search_path nas 5 funções de segurança (proconfig não nulo).
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.proconfig IS NOT NULL "
            "AND p.proname IN ('custom_access_token_hook', 'app_current_claims', "
            "'app_setor', 'app_is_admin', 'app_current_user_id')",
        )
        == 5
    ), "0006 deve fixar search_path nas 5 funções de segurança"
    # W2-C06: tabela provas (0007) + RLS por perfil e role de runtime (0008).
    assert _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'provas'") == 1, (
        "0007 deve criar a tabela provas"
    )
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_provas_rota_imutavel'",
        )
        == 1
    ), "0007 deve criar o trigger de imutabilidade da rota (RN-007)"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_policies WHERE tablename = 'provas'") == 6
    ), "0008 deve criar as 6 policies de provas (5 SELECT + 1 INSERT)"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_roles WHERE rolname = 'rastreio_runtime' AND NOT rolbypassrls",
        )
        == 1
    ), "0008 deve criar o role de runtime não-owner (NOBYPASSRLS — ADR-034)"

    command.downgrade(alembic_cfg, "base")
    assert not _pgcrypto_instalada(database_url), "downgrade deve remover a extensão"
    assert _scalar(database_url, "SELECT count(*) FROM alembic_version") == 0, (
        "base deve zerar o histórico de revisões"
    )
    assert _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'usuarios'") == 0, (
        "downgrade da 0002 deve remover a tabela usuarios"
    )
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_type WHERE typname IN ('setor_enum', 'localizacao_enum')",
        )
        == 0
    ), "downgrade da 0002 deve remover os enums de domínio"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc WHERE proname = 'custom_access_token_hook'",
        )
        == 0
    ), "downgrade da 0004 deve remover o hook"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_proc WHERE proname = 'app_is_admin'") == 0
    ), "downgrade da 0005 deve remover os helpers de RLS"
    assert _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'provas'") == 0, (
        "downgrade da 0007 deve remover a tabela provas"
    )
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_type WHERE typname IN ('rota_enum', 'status_prova_enum')",
        )
        == 0
    ), "downgrade da 0007 deve remover os enums de provas"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_proc WHERE proname = 'provas_rota_imutavel'")
        == 0
    ), "downgrade da 0007 deve remover a função do trigger"

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
