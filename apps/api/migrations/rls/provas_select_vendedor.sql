-- Matriz §7 (◐): Vendedor vê APENAS as provas em que é o vendedor responsável.
DROP POLICY IF EXISTS provas_select_vendedor ON provas;
CREATE POLICY provas_select_vendedor ON provas FOR SELECT
    TO authenticated
    USING (public.app_setor() = 'vendedor' AND vendedor_id = public.app_current_user_id());
