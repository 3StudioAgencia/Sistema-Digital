-- alembic_version — postura RLS restritiva (revisão adversarial W1-C04)
--
-- No Supabase, DEFAULT PRIVILEGES de `public` expõem tabelas novas a
-- anon/authenticated via PostgREST — inclusive a tabela de controle do
-- Alembic, que ficaria legível E gravável (vandalizar o version_num quebra
-- as migrations futuras). RLS sem policies + REVOKE fecham o acesso; o
-- Alembic continua operando normalmente (conexão owner).
--
-- Aplicação: executada pela migration 0003 (idempotente); reaplicar
-- manualmente se a tabela for recriada:
--   psql "$MIGRATIONS_DATABASE_URL" -f migrations/rls/alembic_version_baseline_restritiva.sql

ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE alembic_version FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE alembic_version FROM authenticated;
    END IF;
END
$$;
