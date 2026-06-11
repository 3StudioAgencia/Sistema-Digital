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

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    # Downgrade defensivo (W0-A-014): o upgrade é no-op em ambiente gerenciado
    # (Supabase) — a extensão já existe e é COMPARTILHADA. Remover
    # incondicionalmente dropa um recurso que esta migration não criou (ou falha
    # por dependência RESTRICT). Só desfaz em dev/test, onde o ciclo completo
    # (upgrade→downgrade→upgrade) é validado em banco limpo; em staging/produção
    # é no-op — desfaz apenas o registro da revisão.
    app_env = os.environ.get("APP_ENV", "dev").strip().lower()
    if app_env in ("dev", "test"):
        op.execute("DROP EXTENSION IF EXISTS pgcrypto")
