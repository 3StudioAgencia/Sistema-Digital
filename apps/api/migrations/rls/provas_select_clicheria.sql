-- Matriz §7, "Listagem/Visualização de Provas": Clicheria vê TODAS (●).
DROP POLICY IF EXISTS provas_select_clicheria ON provas;
CREATE POLICY provas_select_clicheria ON provas FOR SELECT
    TO authenticated USING (public.app_setor() = 'clicheria');
