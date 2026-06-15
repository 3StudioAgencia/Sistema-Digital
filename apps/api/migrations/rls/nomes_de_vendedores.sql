-- nomes_de_vendedores.sql — projecao SECURITY DEFINER de nomes de vendedor (W2-C07 / DP-7)
--
-- A listagem de provas (C07) mostra a coluna/dropdown "Vendedor" para 3Studio,
-- Clicheria, Admin e Motorista — perfis que enxergam provas de VARIOS vendedores.
-- A RLS de `usuarios` (C05) so deixa admin/self lerem outras linhas, entao um
-- 3Studio/Clicheria NAO-admin ou um Motorista nao conseguiriam resolver o NOME
-- por um JOIN sob a propria sessao (viria NULL). Esta funcao resolve o nome SEM
-- ampliar a Matriz §7: projeta o MINIMO (apenas id+nome, apenas de vendedores).
--
-- SECURITY DEFINER (roda como owner, que ve todas as linhas) + `SET search_path
-- = ''` + corpo schema-qualificado: mesma blindagem dos helpers de RLS (advisor
-- function_search_path_mutable, W1-A-004). Idempotente (CREATE OR REPLACE).
-- EXECUTE revogado de PUBLIC e concedido so a `authenticated` (privilegio minimo).
--
-- Espelho 1:1 da migration 0010 (reaplicar apos qualquer DROP/recriacao).

CREATE OR REPLACE FUNCTION public.nomes_de_vendedores(p_ids uuid[])
RETURNS TABLE (id uuid, nome text)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT u.id, u.nome
    FROM public.usuarios u
    WHERE u.setor = 'vendedor'
      AND u.id = ANY(p_ids);
$$;

REVOKE ALL ON FUNCTION public.nomes_de_vendedores(uuid[]) FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT EXECUTE ON FUNCTION public.nomes_de_vendedores(uuid[]) TO authenticated;
    END IF;
END
$$;
