-- Role de LOGIN não-owner do runtime (W2-C06 — fecha o ADR-034 item 3 / W1-A-001).
--
-- O runtime da API deve conectar como `rastreio_runtime` (NOBYPASSRLS, não-owner)
-- em vez do owner: mesmo que algum caminho de query esqueça a propagação de
-- claims (fail-closed já levanta — ADR-034 item 2), o role de conexão NÃO tem
-- como fazer bypass da RLS. O role só serve para `SET ROLE authenticated`
-- (modelo authenticator); NOINHERIT impede herdar privilégios passivamente.
--
-- Criado NOLOGIN aqui (nenhuma senha é versionada — CLAUDE.md §9). Passo de
-- operação para ativar (dashboard/psql do Supabase e no Postgres local):
--     ALTER ROLE rastreio_runtime LOGIN PASSWORD '<segredo-fora-do-repo>';
-- e apontar DATABASE_URL para ele (no pooler do Supabase: usuário
-- `rastreio_runtime.<project-ref>`). Tarefas de SISTEMA (migrations,
-- bootstrap_admin, keep-alive) continuam no owner via MIGRATIONS_DATABASE_URL.
-- Idempotente.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rastreio_runtime') THEN
        CREATE ROLE rastreio_runtime NOLOGIN NOINHERIT NOBYPASSRLS;
    END IF;
END
$$;
GRANT authenticated TO rastreio_runtime;
