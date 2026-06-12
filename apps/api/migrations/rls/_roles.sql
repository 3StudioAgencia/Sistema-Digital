-- _roles.sql — stand-ins LOCAIS das roles do Supabase (W1-C05 / ADR-031)
--
-- No Supabase, "anon" e "authenticated" sao roles de plataforma que JA existem.
-- Em Postgres limpo (CI/zonky local) elas nao existem — e CREATE POLICY ... TO
-- authenticated / GRANT ... TO authenticated falhariam. Este bloco cria
-- stand-ins minimos (NOLOGIN) APENAS quando ausentes: e no-op no Supabase e
-- torna as migrations de RLS aplicaveis em ambiente limpo (DoD §8).
--
-- Idempotente. Aplicado primeiro (prefixo "_" ordena antes de "usuarios_*").

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
END
$$;
