-- system_settings_grants.sql — privilegios de tabela (W2-C09 / DP-2) — migration 0013
--
-- `authenticated` recebe SELECT, INSERT e UPDATE: a leitura e aberta (a policy
-- de SELECT nao restringe — features de todos os perfis leem o valor); a escrita
-- e travada pelas policies de INSERT/UPDATE (admin-only). O upsert idempotente
-- (INSERT ... ON CONFLICT DO UPDATE) exige INSERT e UPDATE. Nao concede remocao
-- (a app nunca apaga config — privilegio minimo, espelha o criterio de `provas`).
-- `anon` sem acesso. Pre-requisito: RLS ja habilitada na tabela (migration 0013).
-- Idempotente.
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
$$;
