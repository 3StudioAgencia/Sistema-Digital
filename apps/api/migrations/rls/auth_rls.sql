-- Espelho 1:1 da RLS deny-all de auth_credentials/auth_sessions (migration 0023).
-- Reaplicar apos DROP/recriacao. Fonte: apps/api/migrations/versions/0023_auth_local.py.
--
-- Ambas as tabelas: RLS habilitada e SEM policy = negacao por padrao. Nenhum
-- grant de TABELA para anon/authenticated — todo acesso passa pelas funcoes
-- private.auth_* (SECURITY DEFINER). Guarda os hashes de senha e os refresh
-- tokens fora do alcance direto de qualquer role de cliente.

ALTER TABLE auth_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY;

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
$$;
