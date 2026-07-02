-- Espelho 1:1 das funcoes private.auth_* (migration 0023). Reaplicar apos DROP.
-- Fonte da verdade: apps/api/migrations/versions/0023_auth_local.py.
-- SECURITY DEFINER + search_path='' + corpo schema-qualificado (blindagem W1-A-004).
--
-- Duas classes de acesso (ver docstring da 0023):
--  - pre-autenticacao (login/refresh/logout): EXECUTE so ao rastreio_runtime.
--  - provisionamento (sessao do admin): EXECUTE a authenticated + app_is_admin().

-- ============================ PRE-AUTENTICACAO =============================

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
$$;

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
$$;

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
$$;

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
        RETURN;
    END IF;

    INSERT INTO public.auth_sessions (user_id, refresh_hash, expires_at)
    VALUES (v_user_id, p_novo_hash, p_expires_at);

    RETURN QUERY SELECT v_user_id;
END;
$$;

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
$$;

-- ============================ PROVISIONAMENTO ==============================

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
$$;

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
$$;

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
$$;
