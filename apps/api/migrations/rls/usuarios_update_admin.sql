-- usuarios_update_admin.sql — so administrador edita/ativa/desativa (W1-C05)
--
-- Cobre edicao de perfil e mudanca de status (US-015) — todas Exclusivo 3Studio.
-- USING filtra as linhas visiveis ao UPDATE; WITH CHECK barra gravar um estado
-- fora do escopo de admin. As regras de negocio (RN-010 etc.) seguem no dominio.
--
-- Idempotente.

DROP POLICY IF EXISTS usuarios_update_admin ON usuarios;
CREATE POLICY usuarios_update_admin ON usuarios
    FOR UPDATE
    TO authenticated
    USING (public.app_is_admin())
    WITH CHECK (public.app_is_admin());
