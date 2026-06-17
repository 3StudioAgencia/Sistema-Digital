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
    assert _scalar(database_url, "SELECT version_num FROM alembic_version") == "0021", (
        "head deve registrar a revisão 0021 (horas_uteis_entre: função de horas "
        "úteis dos Relatórios — W5-C17)"
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
        _scalar(database_url, "SELECT count(*) FROM pg_policies WHERE tablename = 'provas'") == 11
    ), "provas: 5 SELECT + 1 INSERT (C06) + 5 UPDATE da transição (W3-C11/0015)"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_roles WHERE rolname = 'rastreio_runtime' AND NOT rolbypassrls",
        )
        == 1
    ), "0008 deve criar o role de runtime não-owner (NOBYPASSRLS — ADR-034)"
    # W2-C07: coluna finalizada_em (DP-3) + projetor de nomes de vendedor (DP-7).
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'provas' AND column_name = 'finalizada_em'",
        )
        == 1
    ), "0010 deve adicionar a coluna provas.finalizada_em"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE p.proname = 'nomes_de_vendedores' AND n.nspname = 'private'",
        )
        == 1
    ), "0010+0011 devem deixar nomes_de_vendedores no schema private (DP-7)"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE p.proname = 'nomes_de_vendedores' AND n.nspname = 'public'",
        )
        == 0
    ), "0011 deve mover nomes_de_vendedores para fora do schema public (exposto)"
    # W3 remediação M-02: a 0019 realinha o ramo Motorista do resolvedor aos 6
    # estados operacionais — o corpo da função passa a conter as ORIGENS das
    # transições (ausentes na versão estreita de 3 "Em Trânsito").
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc WHERE proname = 'nomes_de_vendedores' "
            "AND prosrc LIKE '%encaminhada_para_laminacao%'",
        )
        == 1
    ), "0019 deve alinhar nomes_de_vendedores ao escopo ampliado do Motorista (M-02)"
    # W2-C08: coluna ciclo_atual (DP-1), NOT NULL com default 1.
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM information_schema.columns WHERE table_name = 'provas' "
            "AND column_name = 'ciclo_atual' AND is_nullable = 'NO'",
        )
        == 1
    ), "0012 deve adicionar provas.ciclo_atual NOT NULL (DP-1)"
    # W3-C15: 0018 acrescenta ciclo_atual ao GRANT de UPDATE de provas a authenticated
    # (o Reinício de Ciclo incrementa o contador — sem o grant, "permission denied").
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM information_schema.column_privileges "
            "WHERE table_name = 'provas' AND column_name = 'ciclo_atual' "
            "AND privilege_type = 'UPDATE' AND grantee = 'authenticated'",
        )
        == 1
    ), "0018 deve conceder UPDATE(ciclo_atual) em provas a authenticated (W3-C15)"
    # W2-C09: tabela system_settings (0013) + RLS (leitura authenticated, escrita admin).
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'system_settings'")
        == 1
    ), "0013 deve criar a tabela system_settings"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_policies WHERE tablename = 'system_settings'",
        )
        == 3
    ), "0013 deve criar as 3 policies de system_settings (1 SELECT + INSERT + UPDATE)"
    # W3-C10: tabela rate_limit_contadores (0014) + RLS por ator (1 policy FOR ALL).
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_class WHERE relname = 'rate_limit_contadores'",
        )
        == 1
    ), "0014 deve criar a tabela rate_limit_contadores"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_policies WHERE tablename = 'rate_limit_contadores'",
        )
        == 1
    ), "0014 deve criar a policy rate_limit_contadores_self (FOR ALL — ator só a própria linha)"
    # W3-C11: tabela movimentacoes (0015) append-only + acao_enum + RLS.
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'movimentacoes'") == 1
    ), "0015 deve criar a tabela movimentacoes"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_type WHERE typname = 'acao_enum'") == 1
    ), "0015 deve criar o tipo acao_enum (sincronizado com domain/state_machine)"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_movimentacoes_append_only'",
        )
        == 1
    ), "0015 deve criar o trigger append-only (RNF-006: imutável)"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_policies WHERE tablename = 'movimentacoes'",
        )
        == 2
    ), "0015 deve criar as 2 policies de movimentacoes (SELECT por prova visível + INSERT)"
    # W3-C12: tabela assinaturas (0016) append-only + RLS + FK do C11.
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'assinaturas'") == 1
    ), "0016 deve criar a tabela assinaturas"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_assinaturas_append_only'",
        )
        == 1
    ), "0016 deve criar o trigger append-only de assinaturas (RN-003: imutável)"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_policies WHERE tablename = 'assinaturas'",
        )
        == 2
    ), "0016 deve criar as 2 policies de assinaturas (SELECT por prova visível + INSERT)"
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM information_schema.table_constraints "
            "WHERE constraint_name = 'fk_movimentacoes_assinatura_ref_assinaturas' "
            "AND constraint_type = 'FOREIGN KEY'",
        )
        == 1
    ), "0016 deve fechar a FK movimentacoes.assinatura_ref -> assinaturas (DP-1)"
    # W3-C13: projetor de nomes de ator (DP-2b) no schema private (não exposto).
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE p.proname = 'nomes_de_usuarios' AND n.nspname = 'private'",
        )
        == 1
    ), "0017 deve criar nomes_de_usuarios no schema private (DP-2b)"
    # W4-C16: função de horas úteis do Dashboard (0020), no schema private (não exposto).
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE p.proname = 'instante_limite_atraso' AND n.nspname = 'private'",
        )
        == 1
    ), "0020 deve criar private.instante_limite_atraso (horas úteis — W4-C16)"
    # W5-C17: função de duração em horas úteis dos Relatórios (0021), schema private.
    assert (
        _scalar(
            database_url,
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE p.proname = 'horas_uteis_entre' AND n.nspname = 'private'",
        )
        == 1
    ), "0021 deve criar private.horas_uteis_entre (horas úteis — W5-C17)"

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
        _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'assinaturas'") == 0
    ), "downgrade da 0016 deve remover a tabela assinaturas"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'movimentacoes'") == 0
    ), "downgrade da 0015 deve remover a tabela movimentacoes"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_type WHERE typname = 'acao_enum'") == 0
    ), "downgrade da 0015 deve remover o tipo acao_enum"
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
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_proc WHERE proname = 'nomes_de_vendedores'")
        == 0
    ), "downgrade da 0010 deve remover a função nomes_de_vendedores"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_proc WHERE proname = 'nomes_de_usuarios'")
        == 0
    ), "downgrade da 0017 deve remover a função nomes_de_usuarios"
    assert (
        _scalar(
            database_url, "SELECT count(*) FROM pg_proc WHERE proname = 'instante_limite_atraso'"
        )
        == 0
    ), "downgrade da 0020 deve remover a função instante_limite_atraso"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_proc WHERE proname = 'horas_uteis_entre'")
        == 0
    ), "downgrade da 0021 deve remover a função horas_uteis_entre"
    assert (
        _scalar(database_url, "SELECT count(*) FROM pg_class WHERE relname = 'system_settings'")
        == 0
    ), "downgrade da 0013 deve remover a tabela system_settings"
    assert (
        _scalar(
            database_url, "SELECT count(*) FROM pg_class WHERE relname = 'rate_limit_contadores'"
        )
        == 0
    ), "downgrade da 0014 deve remover a tabela rate_limit_contadores"

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
