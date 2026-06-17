-- nomes_de_vendedores.sql — projecao SECURITY DEFINER de nomes de vendedor (W2-C07 / DP-7)
--
-- A listagem de provas (C07) mostra a coluna/dropdown "Vendedor" para 3Studio,
-- Clicheria, Admin e Motorista — perfis que enxergam provas de VARIOS vendedores.
-- A RLS de `usuarios` (C05) so deixa admin/self lerem outras linhas, entao um
-- 3Studio/Clicheria NAO-admin ou um Motorista nao conseguiriam resolver o NOME
-- por um JOIN sob a propria sessao (viria NULL). Esta funcao resolve o nome SEM
-- ampliar a Matriz §7: projeta o MINIMO (apenas id+nome, apenas de vendedores).
--
-- SCHEMA `private` (NAO exposto pela Data API/PostgREST — migrations 0010 criou
-- em public, 0011 moveu para private): a funcao e um resolvedor INTERNO chamado
-- pelo backend, nao um RPC publico. Mover para fora do schema exposto elimina o
-- vetor de RPC (advisors 0028/0029) — as DEFAULT PRIVILEGES do Supabase so
-- concedem EXECUTE as roles de API para objetos de `public`. So `authenticated`
-- recebe USAGE no schema + EXECUTE na funcao (privilegio minimo; `anon` nao).
--
-- SECURITY DEFINER (roda como owner, ve todas as linhas) + `SET search_path=''`
-- + corpo schema-qualificado (blindagem W1-A-004). DEFESA EM PROFUNDIDADE: o
-- corpo RE-APLICA o escopo do chamador (so resolve nomes de vendedores em provas
-- VISIVEIS a ele — espelha as policies `provas_select_*` via os helpers `app_*`).
-- O ramo `motorista` espelha `provas_select_motorista` AMPLIADA pela 0015
-- (ESTADOS_ESCOPO_MOTORISTA: origens das transicoes + Em Transito — 6 estados),
-- realinhado pela 0019 (remediacao M-02; antes ficara nos 3 "Em Transito" e
-- divergira do irmao `nomes_de_usuarios`). (Drift: este predicado acompanha a RLS
-- de `provas` — mantenha-os em sincronia; o harness offline trava os dois.)
--
-- Idempotente. Espelho 1:1 das migrations 0010+0011+0019 (reaplicar apos DROP).

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;

CREATE OR REPLACE FUNCTION private.nomes_de_vendedores(p_ids uuid[])
RETURNS TABLE (id uuid, nome text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.nome
    FROM public.usuarios u
    WHERE u.setor = 'vendedor'
      AND u.id = ANY(p_ids)
      AND EXISTS (
          SELECT 1 FROM public.provas p
          WHERE p.vendedor_id = u.id AND (
              public.app_is_admin()
              OR public.app_setor() IN ('studio', 'clicheria')
              OR (public.app_setor() = 'vendedor'
                  AND p.vendedor_id = public.app_current_user_id())
              OR (public.app_setor() = 'motorista' AND p.status IN (
                  'encaminhada_para_laminacao',
                  'laminacao_concluida',
                  'de_volta_studio',
                  'com_motorista_ida_laminacao',
                  'com_motorista_volta_laminacao',
                  'com_motorista_entrega_final'))
          )
      );
$$;

REVOKE ALL ON FUNCTION private.nomes_de_vendedores(uuid[]) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.nomes_de_vendedores(uuid[]) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.nomes_de_vendedores(uuid[]) TO authenticated;
    END IF;
END
$$;
