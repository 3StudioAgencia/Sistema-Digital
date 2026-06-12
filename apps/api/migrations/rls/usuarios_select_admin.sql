-- usuarios_select_admin.sql — administrador le TODOS os usuarios (W1-C05)
--
-- Matriz §7, "Cadastro de Usuarios" = Exclusivo 3Studio: chaveia pelo FLAG
-- administrador (ADR-023), nao pelo setor. Sustenta a listagem paginada.
--
-- Idempotente.

DROP POLICY IF EXISTS usuarios_select_admin ON usuarios;
CREATE POLICY usuarios_select_admin ON usuarios
    FOR SELECT
    TO authenticated
    USING (public.app_is_admin());
