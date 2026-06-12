-- usuarios_delete_admin.sql — so administrador remove (W1-C05)
--
-- A app NAO expoe hard-delete de usuarios nesta wave (desativa via ban, US-015),
-- mas a RLS de DELETE existe para fechar a tabela tambem nessa operacao: sem
-- esta policy, nenhum DELETE passa (negacao por padrao). Mantida restrita a
-- admin por simetria com as demais mutacoes.
--
-- Idempotente.

DROP POLICY IF EXISTS usuarios_delete_admin ON usuarios;
CREATE POLICY usuarios_delete_admin ON usuarios
    FOR DELETE
    TO authenticated
    USING (public.app_is_admin());
