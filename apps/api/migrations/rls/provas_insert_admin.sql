-- Matriz §7, "Criar Prova": exclusivo do Administrador (flag — ADR-023).
DROP POLICY IF EXISTS provas_insert_admin ON provas;
CREATE POLICY provas_insert_admin ON provas FOR INSERT
    TO authenticated WITH CHECK (public.app_is_admin());
