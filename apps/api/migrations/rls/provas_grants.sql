-- Privilégios de tabela de `provas` (W2-C06 / DP-6) — aplicado pela migration 0008.
-- `authenticated` recebe SOMENTE SELECT e INSERT: as mutações de transição
-- (UPDATE) são do C11 e o cancelamento/deleção lógica do C14 — os grants e as
-- policies correspondentes chegam lá (privilégio mínimo). `anon` sem acesso.
-- Idempotente: GRANT/REVOKE repetidos não falham nem duplicam.
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
$$;
