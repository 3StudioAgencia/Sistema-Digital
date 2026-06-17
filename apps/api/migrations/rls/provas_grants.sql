-- Privilégios de tabela de `provas` (W2-C06 / DP-6) — base aplicada pela migration
-- 0008; o UPDATE de colunas (status/finalizada_em/updated_at) chega no C11
-- (migration 0015) e `ciclo_atual` no C15 (migration 0018, ver abaixo).
-- `authenticated` recebe SELECT e INSERT; o DELETE (cancelamento é transição
-- lógica → `cancelada`, nunca DELETE físico) nunca é concedido. `anon` sem acesso.
-- Idempotente: GRANT/REVOKE repetidos não falham.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE provas FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE provas FROM authenticated;
        GRANT SELECT, INSERT ON TABLE provas TO authenticated;
        -- Superfície de transição (privilégio mínimo — só estas colunas; nunca
        -- codigo/nome/rota/vendedor_id). status/finalizada_em/updated_at: W3-C11
        -- (migration 0015). ciclo_atual: W3-C15 (migration 0018 — o Reinício de
        -- Ciclo incrementa este contador na transação da transição).
        GRANT UPDATE (status, finalizada_em, updated_at, ciclo_atual)
            ON TABLE provas TO authenticated;
    END IF;
END
$$;
