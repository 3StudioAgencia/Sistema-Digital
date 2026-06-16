"""rate_limit_contadores — contador de tentativas de identificacao (W3-C10)

Cria a tabela ``rate_limit_contadores`` (controle de abuso do endpoint
``POST /provas/identificar`` — RN-014: 30 tentativas/usuario/minuto). UMA linha
por ``(user_id, chave)``: o limitador faz upsert atomico que incrementa na janela
de 1 minuto e RESETA ao virar o minuto — armazenamento limitado ao numero de
atores, sem job de limpeza.

RLS (defesa em profundidade): o ator so ve/grava a PROPRIA linha
(``user_id = app_current_user_id()``) — um ator nunca le nem incrementa o contador
de outro. O ``user_id`` ja vem de ``app_current_user_id()`` no upsert; a policy e
a rede de seguranca. authenticated recebe SELECT/INSERT/UPDATE (o upsert
idempotente le o RETURNING e atualiza a janela); sem DELETE (a app nunca apaga).

Espelho 1:1 em ``migrations/rls/rate_limit_contadores_*.sql`` (DAT §2; reaplicar
apos recriacao da tabela). Instrucoes SEPARADAS (asyncpg nao aceita multiplos
comandos por instrucao preparada — mesmo motivo do 0008/0013).

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_ENABLE = "ALTER TABLE rate_limit_contadores ENABLE ROW LEVEL SECURITY"

# --- grants (espelho: rate_limit_contadores_grants.sql) ---------------------
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE rate_limit_contadores FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE rate_limit_contadores FROM authenticated;
        GRANT SELECT, INSERT, UPDATE ON TABLE rate_limit_contadores TO authenticated;
    END IF;
END
$$
"""

# --- policy (espelho: rate_limit_contadores_self.sql) -----------------------
_POLICY_NOME = "rate_limit_contadores_self"
_POLICY = (
    "CREATE POLICY rate_limit_contadores_self ON rate_limit_contadores FOR ALL "
    "TO authenticated "
    "USING (user_id = public.app_current_user_id()) "
    "WITH CHECK (user_id = public.app_current_user_id())"
)


def upgrade() -> None:
    op.create_table(
        "rate_limit_contadores",
        # Ator dono do contador (= sub/user_id do JWT). Sem FK para usuarios: o
        # contador e efemero e nao deve travar nada (mesma filosofia do
        # system_settings.updated_by).
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        # Bucket logico (ex.: "identificar") — a tabela serve varios endpoints.
        sa.Column("chave", sa.String(length=60), nullable=False),
        # Inicio da janela fixa (date_trunc('minute', now())).
        sa.Column("janela_inicio", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("contador", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("user_id", "chave", name="pk_rate_limit_contadores"),
    )

    op.execute(_RLS_ENABLE)
    op.execute(_GRANTS)
    op.execute(f"DROP POLICY IF EXISTS {_POLICY_NOME} ON rate_limit_contadores")
    op.execute(_POLICY)


def downgrade() -> None:
    op.drop_table("rate_limit_contadores")  # policy e grants caem junto com a tabela
