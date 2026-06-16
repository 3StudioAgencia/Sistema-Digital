-- rate_limit_contadores_grants.sql — privilegio minimo do contador (W3-C10)
--
-- authenticated faz o upsert (INSERT ... ON CONFLICT DO UPDATE) e le o proprio
-- contador (RETURNING/SELECT). Sem DELETE: a app nunca apaga linhas (o upsert
-- reseta a janela ao virar o minuto). anon nao toca a tabela.
--
-- Idempotente. Reaplicar apos qualquer DROP/recriacao da tabela (CLAUDE.md §9).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE rate_limit_contadores FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE rate_limit_contadores FROM authenticated;
        GRANT SELECT, INSERT, UPDATE ON TABLE rate_limit_contadores TO authenticated;
    END IF;
END
$$;
