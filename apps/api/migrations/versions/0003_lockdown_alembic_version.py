"""lockdown da alembic_version no PostgREST (revisao adversarial W1-C04)

No Supabase, DEFAULT PRIVILEGES do schema public concedem acesso de
anon/authenticated a TODA tabela nova — inclusive a ``alembic_version`` criada
pelo proprio Alembic. Sem RLS nem REVOKE, ela fica legivel E gravavel via
PostgREST por qualquer chave anon: vandalizar o version_num quebra todas as
migrations futuras. Esta migration habilita RLS (sem policies = negacao por
padrao) e revoga os privilegios das roles do Supabase, condicionalmente a
existencia delas (o Postgres local de dev/teste nao as tem).

Espelho versionado: ``migrations/rls/alembic_version_baseline_restritiva.sql``.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_ENABLE = "ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY"
_RLS_REVOKE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE alembic_version FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE alembic_version FROM authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.execute(_RLS_ENABLE)
    op.execute(_RLS_REVOKE)


def downgrade() -> None:
    # Desfaz apenas a RLS (os REVOKE permanecem — restaurar privilégio de
    # cliente anônimo sobre a tabela de controle nunca é desejável).
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
