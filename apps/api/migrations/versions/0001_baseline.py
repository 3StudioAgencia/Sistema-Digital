"""baseline — valida o pipeline de migrations; SEM tabelas de domínio

Habilita a extensão pgcrypto (provê gen_random_uuid(), usada pelas tabelas de
domínio a partir da Wave 2). Idempotente: no Supabase a extensão costuma já
existir e o IF NOT EXISTS torna a operação um no-op seguro.

Tabelas de domínio (usuarios, provas_digitais, movimentacoes, ...) chegam nos
componentes 04/06/09 — NÃO nesta wave (prompt W0-C01 §2).

Revision ID: 0001
Revises:
Create Date: 2026-06-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    # Atenção em ambientes gerenciados (Supabase): a extensão pode ser
    # compartilhada com outros recursos. O downgrade existe para validar o
    # ciclo completo em ambiente limpo (critério de aceitação §5.1).
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
