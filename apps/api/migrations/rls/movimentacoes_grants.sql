-- Privilegios de `movimentacoes` (W3-C11) — aplicado pela migration 0015.
-- APPEND-ONLY (RNF-006): `authenticated` recebe SOMENTE SELECT e INSERT. UPDATE e
-- DELETE NUNCA sao concedidos (privilegio minimo) e o trigger
-- `trg_movimentacoes_append_only` os bloqueia ate para o owner. `anon` sem acesso.
-- Idempotente.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE movimentacoes FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE movimentacoes FROM authenticated;
        GRANT SELECT, INSERT ON TABLE movimentacoes TO authenticated;
    END IF;
END
$$;
