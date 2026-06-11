-- usuarios — postura RLS RESTRITIVA provisória (W1-C04 / DP-5 / ADR-027)
--
-- A tabela NÃO pode nascer exposta: RLS habilitada e SEM policies para
-- anon/authenticated (negação por padrão no PostgREST/cliente Supabase) +
-- privilégios revogados (cinto e suspensório). O dado é servido EXCLUSIVAMENTE
-- pelo backend (conexão owner via DATABASE_URL), atrás do guard de admin.
--
-- As policies POR PERFIL (matriz de acesso §7) chegam no W1-C05 — uma por
-- perfil × operação, em arquivos próprios nesta pasta (README).
--
-- Aplicação: executada pela migration Alembic 0002 (idempotente); reaplicar
-- manualmente após qualquer recriação da tabela:
--   psql "$MIGRATIONS_DATABASE_URL" -f migrations/rls/usuarios_baseline_restritiva.sql

ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE usuarios FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE usuarios FROM authenticated;
    END IF;
END
$$;
