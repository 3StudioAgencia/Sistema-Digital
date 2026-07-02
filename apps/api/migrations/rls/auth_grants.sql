-- Espelho 1:1 dos grants de EXECUTE das funcoes private.auth_* (migration 0023).
-- Reaplicar apos DROP/recriacao. Fonte: apps/api/migrations/versions/0023_auth_local.py.
--
-- Duas classes de acesso:
--  - PRE-AUTENTICACAO (login/refresh/logout — sem claims): EXECUTE SO ao
--    rastreio_runtime (o role de conexao do sistema). NUNCA a authenticated —
--    senao um usuario logado colheria o hash de senha alheio via
--    auth_credencial_por_email.
--  - PROVISIONAMENTO (sessao RLS do admin): EXECUTE a authenticated; a checagem
--    app_is_admin() por dentro da funcao e a defesa em profundidade.

DO $$
BEGIN
    REVOKE ALL ON FUNCTION private.auth_credencial_por_email(text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_perfil_para_token(uuid) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_criar_sessao(uuid, text, timestamptz) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_rotacionar_sessao(text, text, timestamptz) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_revogar_sessao(text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_criar_credencial(uuid, text, text) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_remover_credencial(uuid) FROM PUBLIC;
    REVOKE ALL ON FUNCTION private.auth_revogar_sessoes_do_usuario(uuid) FROM PUBLIC;

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

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.auth_criar_credencial(uuid, text, text) TO authenticated;
        GRANT EXECUTE ON FUNCTION private.auth_remover_credencial(uuid) TO authenticated;
        GRANT EXECUTE ON FUNCTION private.auth_revogar_sessoes_do_usuario(uuid) TO authenticated;
    END IF;
END
$$;
