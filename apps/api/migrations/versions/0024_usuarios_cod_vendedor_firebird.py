"""usuarios: cod_vendedor_firebird — mapeia o vendedor do app ao COD_VENDE do ERP (Fatia 3)

Aditiva. Liga cada usuario VENDEDOR do app ao seu codigo no Firebird
(``TB_VENDEDOR.COD_VENDE``): na criacao de prova por requerimento, o backend resolve
o ``COD_VENDE`` do requerimento e casa com o usuario que tem esse codigo, definindo
``provas.vendedor_id`` sozinho — a RLS "vendedor so ve as suas" segue intacta.

- NULLABLE: nem todo vendedor mapeia (e nenhum outro setor tem codigo).
- UNIQUE PARCIAL: um ``COD_VENDE`` -> no maximo um usuario (evita ambiguidade no
  mapeamento). Parcial (``WHERE ... IS NOT NULL``) para nao colidir varios NULLs.
- CHECK: so setor vendedor pode ter codigo (espelha a regra de dominio).

Grant: ``usuarios`` ja tem GRANT de TABELA a ``authenticated`` (0005) — a nova
coluna e coberta automaticamente (sem grant de coluna). RLS de LINHA inalterada
(nenhuma policy nova; o mapeamento e lido sob a sessao do admin, que ve todos).

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK = "ck_usuarios_cod_vendedor_firebird_setor"


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column("cod_vendedor_firebird", sa.Integer(), nullable=True),
    )
    op.create_index(
        "uq_usuarios_cod_vendedor_firebird",
        "usuarios",
        ["cod_vendedor_firebird"],
        unique=True,
        postgresql_where=sa.text("cod_vendedor_firebird IS NOT NULL"),
    )
    # Nome explicito (evita ambiguidade da naming convention no downgrade).
    op.execute(
        f"ALTER TABLE usuarios ADD CONSTRAINT {_CHECK} "
        "CHECK (cod_vendedor_firebird IS NULL OR setor = 'vendedor')"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS {_CHECK}")
    op.drop_index("uq_usuarios_cod_vendedor_firebird", "usuarios")
    op.drop_column("usuarios", "cod_vendedor_firebird")
