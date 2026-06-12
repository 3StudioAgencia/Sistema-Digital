-- Administrador (flag, ortogonal ao setor — ADR-023) vê TODAS: quem pode criar
-- provas (criar_prova = admin) precisa enxergar o que criou, mesmo que seu
-- setor operacional seja restrito (ex.: Vendedor-Admin). Espelha
-- usuarios_select_admin (decisão DP-6 do C06).
DROP POLICY IF EXISTS provas_select_admin ON provas;
CREATE POLICY provas_select_admin ON provas FOR SELECT
    TO authenticated USING (public.app_is_admin());
