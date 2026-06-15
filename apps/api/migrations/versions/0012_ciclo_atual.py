"""ciclo_atual em provas — contador de ciclos de revisao (W2-C08 / DP-1)

Aditiva e nao destrutiva (greenfield; sem dados legados — CLAUDE.md §2.1):

- coluna ``provas.ciclo_atual integer NOT NULL DEFAULT 1`` (DP-1): o numero do
  ciclo de revisao exibido no DETALHE da prova ("Ciclo Atual: 1"). Nasce 1 na
  criacao (server default — o caminho de criacao do C06 nao a informa) e e
  INCREMENTADO pelo C15 (Reinicio de Ciclo) nas transicoes de reinicio. O C08 so
  LE e exibe. Sem indice: nao e coluna de filtro/ordenacao da listagem (RNF-019).

Nao mexe na RLS de ``provas`` (C06): a coluna herda as policies da tabela
(``provas_select_*``); nenhum espelho novo em ``migrations/rls/``.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOT NULL com server default 1: provas existentes (nenhuma no greenfield, mas
    # robusto) recebem ciclo 1; criacao do C06 nao informa a coluna e cai no
    # default (eager_defaults traz o valor no RETURNING — mesmo padrao de status).
    op.add_column(
        "provas",
        sa.Column("ciclo_atual", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("provas", "ciclo_atual")
