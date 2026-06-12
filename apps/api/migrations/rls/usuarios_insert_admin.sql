-- usuarios_insert_admin.sql — so administrador cria usuarios (W1-C05)
--
-- Matriz §7 "Cadastro de Usuarios" = Exclusivo 3Studio (flag administrador).
-- O INSERT da linha de dominio no provisionamento (UsuariosService.criar) corre
-- no backend sob SET ROLE authenticated + claims do admin (ADR-008): o WITH
-- CHECK garante que so um admin insere, na camada do banco.
--
-- Idempotente.

DROP POLICY IF EXISTS usuarios_insert_admin ON usuarios;
CREATE POLICY usuarios_insert_admin ON usuarios
    FOR INSERT
    TO authenticated
    WITH CHECK (public.app_is_admin());
