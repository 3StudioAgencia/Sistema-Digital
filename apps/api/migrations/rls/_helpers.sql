-- _helpers.sql — funcoes reutilizaveis de RLS (W1-C05 / ADR-031)
--
-- Leem os claims propagados a sessao do Postgres (request.jwt.claims), populados
-- pela camada que serve o dado:
--   * via PostgREST/Supabase  -> o GoTrue seta request.jwt.claims;
--   * via backend FastAPI      -> a propagacao da UoW (ADR-008) executa
--     set_config('request.jwt.claims', <json>, true) por transacao.
-- Sao o MESMO conteudo que "auth.jwt()" le no Supabase (DAT §7.2), porem
-- PORTATEIS: nao dependem do schema "auth" (ausente em Postgres local).
--
-- O C06 compoe a RLS de "provas" sobre estes helpers (DP-3), garantindo leitura
-- consistente de setor/user_id/flag em todas as tabelas sensiveis.
--
-- Idempotente (CREATE OR REPLACE). STABLE + SECURITY INVOKER: so leem um GUC,
-- nenhum acesso a tabela.

-- Claims do JWT propagados a sessao (objeto vazio quando ausentes).
CREATE OR REPLACE FUNCTION public.app_current_claims()
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        NULLIF(current_setting('request.jwt.claims', true), ''),
        '{}'
    )::jsonb;
$$;

-- Setor operacional do usuario corrente (NULL quando sem claim).
CREATE OR REPLACE FUNCTION public.app_setor()
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT public.app_current_claims() ->> 'setor';
$$;

-- Flag de perfil ortogonal (ADR-023) — chaveia as linhas "Exclusivo 3Studio"
-- da Matriz §7. Default false: ausencia de claim nunca concede admin.
CREATE OR REPLACE FUNCTION public.app_is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE((public.app_current_claims() ->> 'administrador')::boolean, false);
$$;

-- UUID do usuario corrente (= sub) — escopo de linha "as proprias" (vendedor no
-- C06; a propria linha em usuarios). NULL quando sem claim.
CREATE OR REPLACE FUNCTION public.app_current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(public.app_current_claims() ->> 'user_id', '')::uuid;
$$;
