-- Privilegios de `audit_log` (W6-C20) — aplicado pela migration 0022.
-- APPEND-ONLY (RNF-006): `authenticated` recebe SOMENTE SELECT (leitura sob a RLS
-- admin-only). A ESCRITA e exclusivamente pela funcao SECURITY DEFINER
-- `private.audit_log_append` — NUNCA INSERT direto (anti-forja do chain). UPDATE e
-- DELETE jamais sao concedidos e o trigger `trg_audit_log_append_only` os bloqueia
-- ate para o owner. `anon` sem acesso. Idempotente.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE audit_log FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE audit_log FROM authenticated;
        GRANT SELECT ON TABLE audit_log TO authenticated;
    END IF;
END
$$;
