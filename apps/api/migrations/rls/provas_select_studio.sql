-- Matriz §7, "Listagem/Visualização de Provas": 3Studio vê TODAS (●).
-- Escopo operacional chaveia pelo SETOR (releitura ADR-023).
DROP POLICY IF EXISTS provas_select_studio ON provas;
CREATE POLICY provas_select_studio ON provas FOR SELECT
    TO authenticated USING (public.app_setor() = 'studio');
