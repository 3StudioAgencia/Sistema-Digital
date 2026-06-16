-- Privilégios de tabela de `provas` (W2-C06 / DP-6) — base aplicada pela migration
-- 0008; o UPDATE de colunas (status/finalizada_em/updated_at) chega no C11
-- (migration 0015, ver abaixo). `authenticated` recebe SELECT e INSERT; o DELETE
-- (cancelamento é transição lógica → `cancelada`, nunca DELETE físico) nunca é
-- concedido. `anon` sem acesso. Idempotente: GRANT/REVOKE repetidos não falham.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE provas FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE provas FROM authenticated;
        GRANT SELECT, INSERT ON TABLE provas TO authenticated;
        -- W3-C11: superfície de transição (privilégio mínimo — só estas 3 colunas;
        -- nunca codigo/nome/rota/vendedor_id). Espelha a migration 0015.
        GRANT UPDATE (status, finalizada_em, updated_at) ON TABLE provas TO authenticated;
    END IF;
END
$$;
