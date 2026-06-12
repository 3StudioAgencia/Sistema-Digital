"""RLS definitiva de usuarios + helpers reutilizaveis (W1-C05)

Liga a camada INFERIOR do RBAC (DAT §7.2) para ``usuarios`` e deixa a fundacao
que o C06 reaproveita em ``provas`` (DP-3):

- ``_roles.sql``: stand-ins de ``anon``/``authenticated`` quando ausentes
  (no-op no Supabase; necessario para CREATE POLICY/GRANT em Postgres limpo).
- ``_helpers.sql``: ``app_current_claims/app_setor/app_is_admin/app_current_user_id``
  — leem ``request.jwt.claims`` (o mesmo que ``auth.jwt()`` le no Supabase),
  portateis e sem acesso a tabela.
- ``usuarios_grants.sql``: SUBSTITUI a postura restritiva do C04 (DP-6 / 6-A) —
  ``authenticated`` ganha privilegios de tabela e a RLS por perfil passa a
  filtrar (defesa em profundidade real, inclusive no caminho do backend que
  serve usuarios sob SET ROLE authenticated + claims — ADR-008).
- policies ``usuarios_*``: admin (flag) le/gerencia todos; qualquer autenticado
  le a propria linha (``/me``).

Espelho versionado 1:1 em ``migrations/rls/*.sql`` (regra do DAT §2; reaplicar
apos recriacao de tabela). As instrucoes correm SEPARADAS (asyncpg nao aceita
multiplos comandos por instrucao preparada — mesmo motivo do 0002).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- roles (stand-ins locais; no-op no Supabase) ---------------------------
_ROLES = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
END
$$
"""

# --- helpers (CREATE OR REPLACE — idempotentes) ----------------------------
_HELPERS = (
    """
    CREATE OR REPLACE FUNCTION public.app_current_claims()
    RETURNS jsonb LANGUAGE sql STABLE AS $$
        SELECT COALESCE(NULLIF(current_setting('request.jwt.claims', true), ''), '{}')::jsonb;
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION public.app_setor()
    RETURNS text LANGUAGE sql STABLE AS $$
        SELECT public.app_current_claims() ->> 'setor';
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION public.app_is_admin()
    RETURNS boolean LANGUAGE sql STABLE AS $$
        SELECT COALESCE((public.app_current_claims() ->> 'administrador')::boolean, false);
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION public.app_current_user_id()
    RETURNS uuid LANGUAGE sql STABLE AS $$
        SELECT NULLIF(public.app_current_claims() ->> 'user_id', '')::uuid;
    $$
    """,
)

# --- grants (substitui a postura restritiva do C04) ------------------------
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE usuarios FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE usuarios TO authenticated;
    END IF;
END
$$
"""

# --- policies (DROP IF EXISTS + CREATE, em pares) --------------------------
_POLICIES = (
    (
        "usuarios_select_self",
        "CREATE POLICY usuarios_select_self ON usuarios FOR SELECT "
        "TO authenticated USING (id = public.app_current_user_id())",
    ),
    (
        "usuarios_select_admin",
        "CREATE POLICY usuarios_select_admin ON usuarios FOR SELECT "
        "TO authenticated USING (public.app_is_admin())",
    ),
    (
        "usuarios_insert_admin",
        "CREATE POLICY usuarios_insert_admin ON usuarios FOR INSERT "
        "TO authenticated WITH CHECK (public.app_is_admin())",
    ),
    (
        "usuarios_update_admin",
        "CREATE POLICY usuarios_update_admin ON usuarios FOR UPDATE "
        "TO authenticated USING (public.app_is_admin()) WITH CHECK (public.app_is_admin())",
    ),
    (
        "usuarios_delete_admin",
        "CREATE POLICY usuarios_delete_admin ON usuarios FOR DELETE "
        "TO authenticated USING (public.app_is_admin())",
    ),
)


def upgrade() -> None:
    op.execute(_ROLES)
    for fn in _HELPERS:
        op.execute(fn)
    op.execute(_GRANTS)
    for nome, create in _POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {nome} ON usuarios")
        op.execute(create)


def downgrade() -> None:
    # Volta a postura restritiva do C04: derruba policies, revoga o grant de
    # authenticated e remove os helpers. Roles stand-in permanecem (inofensivas).
    for nome, _ in _POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {nome} ON usuarios")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON TABLE usuarios FROM authenticated;
            END IF;
        END
        $$
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.app_current_user_id()")
    op.execute("DROP FUNCTION IF EXISTS public.app_is_admin()")
    op.execute("DROP FUNCTION IF EXISTS public.app_setor()")
    op.execute("DROP FUNCTION IF EXISTS public.app_current_claims()")
