-- Privilegios de `assinaturas` (W3-C12) — aplicado pela migration 0016.
-- APPEND-ONLY (RN-003/RNF-006): `authenticated` recebe SOMENTE SELECT e INSERT.
-- UPDATE e DELETE NUNCA sao concedidos (privilegio minimo) e o trigger
-- `trg_assinaturas_append_only` os bloqueia ate para o owner. `anon` sem acesso.
-- Idempotente.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE assinaturas FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE assinaturas FROM authenticated;
        GRANT SELECT, INSERT ON TABLE assinaturas TO authenticated;
    END IF;
END
$$;
