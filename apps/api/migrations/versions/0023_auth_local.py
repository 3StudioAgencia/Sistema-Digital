"""auth_local — credenciais e sessoes de autenticacao PROPRIA (migracao Supabase->local)

Substitui o Supabase Auth (GoTrue) por autenticacao propria em FastAPI. O split
``auth.users`` (Supabase) <-> ``usuarios`` (dominio) vira, LOCALMENTE, o split
``auth_credentials`` <-> ``usuarios`` — mesma ideia, mesmo banco. Cria:

1. ``auth_credentials`` — 1 linha por usuario: ``user_id`` (= usuarios.id), ``email``
   (unico, case-insensitive) e ``senha_hash`` (argon2id, gerado na aplicacao). SEM
   FK fisica para ``usuarios`` (mesma filosofia dos demais ``*_id``; a integridade
   1:1 e garantida pela transacao ATOMICA de criacao — o provisionamento insere
   credencial + linha de dominio juntos).
2. ``auth_sessions`` — refresh tokens ROTATIVOS: guarda o ``refresh_hash`` (SHA-256
   do token opaco — o token cru NUNCA e persistido), ``expires_at`` e ``revoked_at``.
   Suporta rotacao (login/refresh emitem um novo, revogam o antigo) e revogacao
   (logout, desativacao de usuario).
3. Funcoes ``private.auth_*`` (SECURITY DEFINER, ``search_path=''``) — a UNICA porta
   de acesso as duas tabelas (RLS deny-all direto). Modelo de acesso em DUAS classes:
   - PRE-AUTENTICACAO (login/refresh/logout — sem claims, sessao de sistema no role
     de runtime): ``auth_credencial_por_email``, ``auth_perfil_para_token``,
     ``auth_criar_sessao``, ``auth_rotacionar_sessao``, ``auth_revogar_sessao``.
     ``EXECUTE`` concedido SO ao ``rastreio_runtime`` (e ao owner em dev) — NUNCA a
     ``authenticated``: se fosse, qualquer usuario logado colheria o hash de senha
     alheio via ``auth_credencial_por_email``.
   - PROVISIONAMENTO (rodam na sessao RLS do admin): ``auth_criar_credencial``,
     ``auth_remover_credencial``, ``auth_revogar_sessoes_do_usuario``. ``EXECUTE`` a
     ``authenticated`` + checagem ``app_is_admin()`` POR DENTRO (defesa em
     profundidade; o bootstrap do 1o admin insere direto pelo owner, sem a funcao).

RLS: ambas as tabelas com RLS habilitada e SEM policy (deny-all); ``anon`` e
``authenticated`` sem grant de tabela — todo acesso passa pelas funcoes DEFINER.

Espelhos 1:1 em ``migrations/rls/auth_*.sql`` (DAT §2; reaplicar apos DROP).
Instrucoes SEPARADAS (asyncpg nao aceita multiplos comandos por instrucao — mesmo
motivo do 0015/0017/0022).

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Funcoes PRE-AUTENTICACAO (login/refresh/logout) — SECURITY DEFINER.
# Rodam na sessao de SISTEMA (sem claims, role de runtime, sem SET ROLE), por isso
# NAO checam app_is_admin(). EXECUTE concedido SO ao rastreio_runtime.
# ---------------------------------------------------------------------------
_FN_CREDENCIAL_POR_EMAIL = """
CREATE OR REPLACE FUNCTION private.auth_credencial_por_email(p_email text)
RETURNS TABLE (
    user_id uuid, senha_hash text, ativo boolean, setor text,
    administrador boolean, email text, nome text
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT c.user_id, c.senha_hash, u.ativo, u.setor::text,
           u.administrador, u.email, u.nome
    FROM public.auth_credentials c
    JOIN public.usuarios u ON u.id = c.user_id
    WHERE lower(c.email) = lower(p_email);
$$
"""

_FN_PERFIL_PARA_CLAIMS = """
CREATE OR REPLACE FUNCTION private.auth_perfil_para_token(p_user_id uuid)
RETURNS TABLE (
    user_id uuid, ativo boolean, setor text,
    administrador boolean, email text, nome text
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.ativo, u.setor::text, u.administrador, u.email, u.nome
    FROM public.usuarios u
    WHERE u.id = p_user_id;
$$
"""

_FN_CRIAR_SESSAO = """
CREATE OR REPLACE FUNCTION private.auth_criar_sessao(
    p_user_id uuid, p_refresh_hash text, p_expires_at timestamptz
) RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    INSERT INTO public.auth_sessions (user_id, refresh_hash, expires_at)
    VALUES (p_user_id, p_refresh_hash, p_expires_at)
    RETURNING id;
$$
"""

# Rotacao ATOMICA: valida o refresh corrente (existe, nao revogado, nao expirado),
# revoga-o e emite um novo — tudo sob a mesma transacao. Devolve o user_id quando
# valido; NENHUMA linha quando invalido (refresh reusado/expirado/desconhecido).
_FN_ROTACIONAR_SESSAO = """
CREATE OR REPLACE FUNCTION private.auth_rotacionar_sessao(
    p_refresh_hash text, p_novo_hash text, p_expires_at timestamptz
) RETURNS TABLE (user_id uuid)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_user_id uuid;
BEGIN
    UPDATE public.auth_sessions
       SET revoked_at = pg_catalog.now()
     WHERE refresh_hash = p_refresh_hash
       AND revoked_at IS NULL
       AND expires_at > pg_catalog.now()
    RETURNING auth_sessions.user_id INTO v_user_id;

    IF v_user_id IS NULL THEN
        RETURN;  -- refresh invalido/reusado/expirado: nenhuma linha
    END IF;

    INSERT INTO public.auth_sessions (user_id, refresh_hash, expires_at)
    VALUES (v_user_id, p_novo_hash, p_expires_at);

    RETURN QUERY SELECT v_user_id;
END;
$$
"""

_FN_REVOGAR_SESSAO = """
CREATE OR REPLACE FUNCTION private.auth_revogar_sessao(p_refresh_hash text)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    UPDATE public.auth_sessions
       SET revoked_at = pg_catalog.now()
     WHERE refresh_hash = p_refresh_hash
       AND revoked_at IS NULL;
$$
"""

# ---------------------------------------------------------------------------
# Funcoes de PROVISIONAMENTO — rodam na sessao RLS do admin. Checam app_is_admin()
# POR DENTRO (o GUC request.jwt.claims sobrevive ao SECURITY DEFINER). EXECUTE a
# authenticated. O bootstrap do 1o admin insere direto pelo owner (sem estas).
# ---------------------------------------------------------------------------
_FN_CRIAR_CREDENCIAL = """
CREATE OR REPLACE FUNCTION private.auth_criar_credencial(
    p_user_id uuid, p_email text, p_senha_hash text
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF NOT public.app_is_admin() THEN
        RAISE EXCEPTION 'auth_criar_credencial: exige administrador'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    INSERT INTO public.auth_credentials (user_id, email, senha_hash)
    VALUES (p_user_id, lower(p_email), p_senha_hash);
END;
$$
"""

_FN_REMOVER_CREDENCIAL = """
CREATE OR REPLACE FUNCTION private.auth_remover_credencial(p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF NOT public.app_is_admin() THEN
        RAISE EXCEPTION 'auth_remover_credencial: exige administrador'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    DELETE FROM public.auth_credentials WHERE user_id = p_user_id;
END;
$$
"""

_FN_REVOGAR_SESSOES_DO_USUARIO = """
CREATE OR REPLACE FUNCTION private.auth_revogar_sessoes_do_usuario(p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF NOT public.app_is_admin() THEN
        RAISE EXCEPTION 'auth_revogar_sessoes_do_usuario: exige administrador'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE public.auth_sessions
       SET revoked_at = pg_catalog.now()
     WHERE user_id = p_user_id
       AND revoked_at IS NULL;
END;
$$
"""

# --- RLS (deny-all) + grants (espelhos: auth_*.sql) -------------------------
_RLS_ENABLE_CREDENTIALS = "ALTER TABLE auth_credentials ENABLE ROW LEVEL SECURITY"
_RLS_ENABLE_SESSIONS = "ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY"

# Nenhum grant de TABELA para anon/authenticated: todo acesso passa pelas funcoes
# DEFINER. Revoga defensivamente (idempotente) caso um default privilege exista.
_TABLE_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE auth_credentials FROM anon;
        REVOKE ALL ON TABLE auth_sessions FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE auth_credentials FROM authenticated;
        REVOKE ALL ON TABLE auth_sessions FROM authenticated;
    END IF;
END
$$
"""

# Grants de EXECUTE. Duas classes (ver docstring):
# - pre-auth: SO rastreio_runtime (o role de conexao do sistema no login/refresh).
# - provisionamento: authenticated (a sessao do admin).
_FUNCS_GRANTS = """
DO $$
BEGIN
    -- Revoga de PUBLIC tudo (deny-by-default); o pseudo-role public sempre existe.
    REVOKE ALL ON FUNCTION private.auth_credencial_por_email(text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_perfil_para_token(uuid) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_criar_sessao(uuid, text, timestamptz) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_rotacionar_sessao(text, text, timestamptz) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_revogar_sessao(text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_criar_credencial(uuid, text, text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_remover_credencial(uuid) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_revogar_sessoes_do_usuario(uuid) FROM PUBLIC;

    -- Pre-autenticacao: EXCLUSIVO do role de runtime (NUNCA authenticated).
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rastreio_runtime') THEN
        GRANT USAGE ON SCHEMA private TO rastreio_runtime;
        GRANT EXECUTE ON FUNCTION private.auth_credencial_por_email(text) TO rastreio_runtime;
        GRANT EXECUTE ON FUNCTION private.auth_perfil_para_token(uuid) TO rastreio_runtime;
        GRANT EXECUTE ON FUNCTION private.auth_criar_sessao(uuid, text, timestamptz)
            TO rastreio_runtime;
        GRANT EXECUTE ON FUNCTION private.auth_rotacionar_sessao(text, text, timestamptz)
            TO rastreio_runtime;
        GRANT EXECUTE ON FUNCTION private.auth_revogar_sessao(text) TO rastreio_runtime;
    END IF;

    -- Provisionamento: sessao do admin (authenticated) + checagem interna app_is_admin().
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.auth_criar_credencial(uuid, text, text)
            TO authenticated;
        GRANT EXECUTE ON FUNCTION private.auth_remover_credencial(uuid) TO authenticated;
        GRANT EXECUTE ON FUNCTION private.auth_revogar_sessoes_do_usuario(uuid)
            TO authenticated;
    END IF;
END
$$
"""

_FUNCOES_PRE_AUTH = (
    _FN_CREDENCIAL_POR_EMAIL,
    _FN_PERFIL_PARA_CLAIMS,
    _FN_CRIAR_SESSAO,
    _FN_ROTACIONAR_SESSAO,
    _FN_REVOGAR_SESSAO,
)
_FUNCOES_PROVISIONAMENTO = (
    _FN_CRIAR_CREDENCIAL,
    _FN_REMOVER_CREDENCIAL,
    _FN_REVOGAR_SESSOES_DO_USUARIO,
)


def upgrade() -> None:
    op.create_table(
        "auth_credentials",
        # PK = UUID de usuarios.id (o mesmo que vira o ``sub`` do JWT). Sem FK
        # fisica: a criacao e atomica (credencial + linha de dominio na mesma
        # transacao) — mesma filosofia dos demais ``*_id`` sem FK.
        sa.Column("user_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        # Hash argon2id (PHC string, ex.: ``$argon2id$v=19$...``) — cabe em Text.
        sa.Column("senha_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Unicidade case-insensitive do e-mail (login e por e-mail; espelha usuarios).
    op.create_index(
        "uq_auth_credentials_email_lower",
        "auth_credentials",
        [sa.text("lower(email)")],
        unique=True,
    )

    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        # SHA-256 (hex) do refresh token opaco — o token CRU nunca e persistido.
        sa.Column("refresh_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        # NULL = ativo; carimbado no logout/rotacao/desativacao.
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("refresh_hash", name="uq_auth_sessions_refresh_hash"),
    )
    # Revogar todas as sessoes de um usuario (desativacao) sem varredura completa.
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    # Schema private ja existe (0011); guarda mantem a migration robusta isolada.
    op.execute("CREATE SCHEMA IF NOT EXISTS private")
    for fn in (*_FUNCOES_PRE_AUTH, *_FUNCOES_PROVISIONAMENTO):
        op.execute(fn)

    op.execute(_RLS_ENABLE_CREDENTIALS)
    op.execute(_RLS_ENABLE_SESSIONS)
    op.execute(_TABLE_GRANTS)
    op.execute(_FUNCS_GRANTS)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS private.auth_revogar_sessoes_do_usuario(uuid)")
    op.execute("DROP FUNCTION IF EXISTS private.auth_remover_credencial(uuid)")
    op.execute("DROP FUNCTION IF EXISTS private.auth_criar_credencial(uuid, text, text)")
    op.execute("DROP FUNCTION IF EXISTS private.auth_revogar_sessao(text)")
    op.execute("DROP FUNCTION IF EXISTS private.auth_rotacionar_sessao(text, text, timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS private.auth_criar_sessao(uuid, text, timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS private.auth_perfil_para_token(uuid)")
    op.execute("DROP FUNCTION IF EXISTS private.auth_credencial_por_email(text)")
    op.drop_table("auth_sessions")  # indice e RLS caem junto
    op.drop_table("auth_credentials")  # indice e RLS caem junto
