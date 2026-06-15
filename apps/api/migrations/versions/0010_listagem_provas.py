"""listagem de provas — finalizada_em + projecao de nomes de vendedor (W2-C07)

Aditiva e nao destrutiva (greenfield; sem dados legados — CLAUDE.md §2.1):

- coluna ``provas.finalizada_em timestamptz NULL`` (DP-3): carimbo dos estados
  TERMINAIS, populado pelo C11 nas transicoes; o C07 apenas LE e filtra por ele
  ("Finalizada em"). Indice PARCIAL ``ix_provas_finalizada_em`` sobre o NOT NULL
  (RNF-019) — so as provas ja finalizadas entram (a maioria fica NULL ate o C11).

- funcao ``public.nomes_de_vendedores(uuid[]) -> (id, nome)`` (DP-7): projeta
  SOMENTE id+nome de usuarios do setor vendedor. SECURITY DEFINER porque a RLS de
  ``usuarios`` (C05) so deixa admin/self lerem outras linhas — um 3Studio/Clicheria
  NAO-admin ou um Motorista (que veem provas de varios vendedores) nao conseguiriam
  resolver o NOME na coluna/dropdown "Vendedor". A funcao expoe o MINIMO (sem
  email/setor/flag) e so de vendedores, sem ampliar a Matriz §7 (nenhuma policy
  nova em usuarios). ``SET search_path = ''`` + corpo schema-qualificado: mesma
  blindagem dos helpers de RLS (W1-A-004). EXECUTE so para ``authenticated``.

Espelho versionado 1:1 em ``migrations/rls/nomes_de_vendedores.sql`` (DAT §2;
reaplicar apos recriacao). Instrucoes SEPARADAS (asyncpg nao aceita multiplos
comandos por instrucao preparada — mesmo motivo do 0005/0008).

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- funcao de projecao de nomes (espelho: nomes_de_vendedores.sql) ----------
_FUNCAO = """
CREATE OR REPLACE FUNCTION public.nomes_de_vendedores(p_ids uuid[])
RETURNS TABLE (id uuid, nome text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.nome
    FROM public.usuarios u
    WHERE u.setor = 'vendedor'
      AND u.id = ANY(p_ids);
$$
"""
# Privilegio minimo: revoga o EXECUTE default de PUBLIC e concede so a
# authenticated (guardado pela existencia da role, como nas demais migrations).
_FUNCAO_REVOKE = "REVOKE ALL ON FUNCTION public.nomes_de_vendedores(uuid[]) FROM PUBLIC"
_FUNCAO_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.nomes_de_vendedores(uuid[]) TO authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    # nullable=True: provas existentes ficam sem carimbo ate o C11; o filtro
    # "Finalizada em" naturalmente exclui as NULL (NULL >= data e NULL).
    op.add_column(
        "provas",
        sa.Column("finalizada_em", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    # Indice PARCIAL (RNF-019): so as finalizadas; mantem o indice pequeno e
    # serve o filtro/ordenacao por data de finalizacao do C07.
    op.create_index(
        "ix_provas_finalizada_em",
        "provas",
        ["finalizada_em"],
        postgresql_where=sa.text("finalizada_em IS NOT NULL"),
    )

    op.execute(_FUNCAO)
    op.execute(_FUNCAO_REVOKE)
    op.execute(_FUNCAO_GRANT)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.nomes_de_vendedores(uuid[])")
    op.drop_index("ix_provas_finalizada_em", table_name="provas")
    op.drop_column("provas", "finalizada_em")
