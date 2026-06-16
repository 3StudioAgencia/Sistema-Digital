-- nomes_de_usuarios.sql — projecao SECURITY DEFINER de nomes de ator (W3-C13 / DP-2b)
--
-- A Timeline (C13) mostra o RESPONSAVEL de cada movimentacao, que pode ser de
-- QUALQUER setor (3Studio/Motorista/Clicheria/Vendedor). A RLS de `usuarios`
-- (C05) so deixa admin/self lerem outras linhas, entao um Vendedor vendo a
-- propria prova nao resolveria o NOME de quem a movimentou por um JOIN sob a
-- propria sessao (viria NULL). Esta funcao resolve o nome SEM ampliar a Matriz §7:
-- projeta o MINIMO (apenas id+nome) e SO de atores em provas VISIVEIS ao chamador.
-- Generaliza `nomes_de_vendedores` (0010/0011) para qualquer setor.
--
-- SCHEMA `private` (NAO exposto pela Data API/PostgREST): a funcao e um resolvedor
-- INTERNO chamado pelo backend, nao um RPC publico — sem vetor de RPC (advisors
-- 0028/0029 limpos). So `authenticated` recebe USAGE no schema + EXECUTE na funcao
-- (privilegio minimo; `anon` nao).
--
-- SECURITY DEFINER (roda como owner, ve todas as linhas) + `SET search_path=''` +
-- corpo schema-qualificado (blindagem W1-A-004). DEFESA EM PROFUNDIDADE: o corpo
-- RE-APLICA o escopo do chamador (so resolve nomes de atores em provas VISIVEIS a
-- ele — espelha as policies `provas_select_*` via os helpers `app_*`). O conjunto
-- de status do Motorista espelha `provas_select_motorista` AMPLIADA pela 0015
-- (origens das transicoes + Em Transito). (Drift: este predicado acompanha a RLS
-- de `provas` — mantenha-os em sincronia.)
--
-- Idempotente. Espelho 1:1 da migration 0017 (reaplicar apos DROP).

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC;

CREATE OR REPLACE FUNCTION private.nomes_de_usuarios(p_ids uuid[])
RETURNS TABLE (id uuid, nome text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.nome
    FROM public.usuarios u
    WHERE u.id = ANY(p_ids)
      AND EXISTS (
          SELECT 1
          FROM public.movimentacoes m
          JOIN public.provas p ON p.id = m.prova_id
          WHERE m.ator_id = u.id AND (
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

REVOKE ALL ON FUNCTION private.nomes_de_usuarios(uuid[]) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON FUNCTION private.nomes_de_usuarios(uuid[]) FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT USAGE ON SCHEMA private TO authenticated;
        GRANT EXECUTE ON FUNCTION private.nomes_de_usuarios(uuid[]) TO authenticated;
    END IF;
END
$$;
