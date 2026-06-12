"""RLS definitiva de provas + role de runtime nao-owner (W2-C06)

Liga a camada INFERIOR do RBAC para ``provas`` (DP-6) e fecha o item 3 do
ADR-034 (W1-A-001):

- ``provas_grants.sql``: SUBSTITUI a postura restritiva da 0007 —
  ``authenticated`` ganha SOMENTE SELECT e INSERT (UPDATE e do C11, DELETE do
  C14 — privilegio minimo).
- policies ``provas_*``: studio/clicheria/admin veem todas; vendedor apenas as
  proprias (``vendedor_id = app_current_user_id()``); motorista apenas as
  "Em Transito" (os tres contextos "Com Motorista" da v1.0); INSERT exclusivo
  do flag admin (Matriz §7 + releitura ADR-023).
- ``_runtime_role.sql``: cria ``rastreio_runtime`` (NOLOGIN NOINHERIT
  NOBYPASSRLS, membro de ``authenticated``) — o login/senha e passo de operacao
  fora do repo (nenhum segredo versionado).

Espelho versionado 1:1 em ``migrations/rls/*.sql`` (DAT §2; reaplicar apos
recriacao da tabela). Instrucoes SEPARADAS (asyncpg nao aceita multiplos
comandos por instrucao preparada — mesmo motivo do 0005).

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- role de runtime nao-owner (espelho: _runtime_role.sql) -----------------
_RUNTIME_ROLE = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rastreio_runtime') THEN
        CREATE ROLE rastreio_runtime NOLOGIN NOINHERIT NOBYPASSRLS;
    END IF;
END
$$
"""
_RUNTIME_ROLE_GRANT = "GRANT authenticated TO rastreio_runtime"

# --- grants (espelho: provas_grants.sql) ------------------------------------
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE provas FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE provas FROM authenticated;
        GRANT SELECT, INSERT ON TABLE provas TO authenticated;
    END IF;
END
$$
"""

# --- policies (espelho: provas_<operacao>_<perfil>.sql) ---------------------
_POLICIES = (
    (
        "provas_select_studio",
        "CREATE POLICY provas_select_studio ON provas FOR SELECT "
        "TO authenticated USING (public.app_setor() = 'studio')",
    ),
    (
        "provas_select_clicheria",
        "CREATE POLICY provas_select_clicheria ON provas FOR SELECT "
        "TO authenticated USING (public.app_setor() = 'clicheria')",
    ),
    (
        "provas_select_admin",
        "CREATE POLICY provas_select_admin ON provas FOR SELECT "
        "TO authenticated USING (public.app_is_admin())",
    ),
    (
        "provas_select_vendedor",
        "CREATE POLICY provas_select_vendedor ON provas FOR SELECT "
        "TO authenticated USING (public.app_setor() = 'vendedor' "
        "AND vendedor_id = public.app_current_user_id())",
    ),
    (
        "provas_select_motorista",
        "CREATE POLICY provas_select_motorista ON provas FOR SELECT "
        "TO authenticated USING (public.app_setor() = 'motorista' "
        "AND status IN ('com_motorista_ida_laminacao', "
        "'com_motorista_volta_laminacao', 'com_motorista_entrega_final'))",
    ),
    (
        "provas_insert_admin",
        "CREATE POLICY provas_insert_admin ON provas FOR INSERT "
        "TO authenticated WITH CHECK (public.app_is_admin())",
    ),
)


def upgrade() -> None:
    op.execute(_RUNTIME_ROLE)
    op.execute(_RUNTIME_ROLE_GRANT)
    op.execute(_GRANTS)
    for nome, create in _POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {nome} ON provas")
        op.execute(create)


def downgrade() -> None:
    # Volta a postura restritiva da 0007: derruba policies e revoga o grant.
    # O role rastreio_runtime permanece (inofensivo sem LOGIN — mesmo criterio
    # das roles stand-in da 0005).
    for nome, _ in _POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {nome} ON provas")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON TABLE provas FROM authenticated;
            END IF;
        END
        $$
        """
    )
