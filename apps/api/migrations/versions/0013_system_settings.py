"""system_settings — configuracoes do sistema chave-valor (W2-C09)

Cria a tabela ``system_settings`` (DP-1: ``key`` text PK, ``value`` JSONB,
``updated_at``, ``updated_by``) que guarda as SOBRESCRITAS das chaves conhecidas
(os defaults e a validacao vivem no dominio — ``src/domain/settings.py``).
RF-022/RN-008/RN-011.

RLS (DP-2/DP-3): leitura ``authenticated`` (o valor — tempo de atraso, template
da etiqueta — alimenta features de todos os perfis: dashboard C16, etiqueta C06,
lidas server-side na sessao RLS do request); ESCRITA exclusiva do flag admin
(Matriz §7 "Configuracoes" = Exclusivo 3Studio, ADR-023). Privilegio minimo:
authenticated recebe SELECT/INSERT/UPDATE (o upsert idempotente usa INSERT ...
ON CONFLICT DO UPDATE); sem DELETE (a app nunca apaga config).

Espelho 1:1 em ``migrations/rls/system_settings_*.sql`` (DAT §2; reaplicar apos
recriacao da tabela). Instrucoes SEPARADAS (asyncpg nao aceita multiplos comandos
por instrucao preparada — mesmo motivo do 0008).

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_ENABLE = "ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY"

# --- grants (espelho: system_settings_grants.sql) ---------------------------
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE system_settings FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE system_settings FROM authenticated;
        GRANT SELECT, INSERT, UPDATE ON TABLE system_settings TO authenticated;
    END IF;
END
$$
"""

# --- policies (espelho: system_settings_<operacao>_<perfil>.sql) ------------
_POLICIES = (
    (
        "system_settings_select_authenticated",
        "CREATE POLICY system_settings_select_authenticated ON system_settings FOR SELECT "
        "TO authenticated USING (true)",
    ),
    (
        "system_settings_insert_admin",
        "CREATE POLICY system_settings_insert_admin ON system_settings FOR INSERT "
        "TO authenticated WITH CHECK (public.app_is_admin())",
    ),
    (
        "system_settings_update_admin",
        "CREATE POLICY system_settings_update_admin ON system_settings FOR UPDATE "
        "TO authenticated USING (public.app_is_admin()) WITH CHECK (public.app_is_admin())",
    ),
)


def upgrade() -> None:
    op.create_table(
        "system_settings",
        # Chave conhecida (delay_horas_uteis, etiqueta_template, ...). O registro
        # de dominio define tipo/validacao/default por chave.
        sa.Column("key", sa.String(length=80), primary_key=True),
        # Valor heterogeneo (escalar ou objeto) — JSONB.
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # UUID do admin que salvou (auditoria leve). Sem FK: usuarios nunca e
        # deletado (apenas desativado — US-015) e isto evita acoplar a tabela.
        sa.Column("updated_by", sa.Uuid(as_uuid=False), nullable=True),
    )

    op.execute(_RLS_ENABLE)
    op.execute(_GRANTS)
    for nome, create in _POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {nome} ON system_settings")
        op.execute(create)


def downgrade() -> None:
    op.drop_table("system_settings")  # policies e grants caem junto com a tabela
