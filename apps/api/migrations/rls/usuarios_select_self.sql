-- usuarios_select_self.sql — cada usuario le a PROPRIA linha (W1-C05)
--
-- Alimenta GET /usuarios/me (saudacao/escopo do app shell) para QUALQUER perfil
-- autenticado, sem expor o cadastro alheio. Combina (OR) com a policy de admin:
-- admin ve todas; nao-admin ve apenas a si mesmo.
--
-- Idempotente (DROP IF EXISTS + CREATE).

DROP POLICY IF EXISTS usuarios_select_self ON usuarios;
CREATE POLICY usuarios_select_self ON usuarios
    FOR SELECT
    TO authenticated
    USING (id = public.app_current_user_id());
