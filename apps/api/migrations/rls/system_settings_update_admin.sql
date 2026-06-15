-- system_settings_update_admin.sql — edicao exclusiva do admin (W2-C09 / DP-3)
--
-- O ramo DO UPDATE do upsert (quando a chave ja existe) corre como UPDATE: so o
-- flag administrador grava. USING filtra as linhas visiveis ao UPDATE; WITH CHECK
-- barra gravar fora do escopo de admin (espelha usuarios_update_admin).
--
-- Idempotente.
DROP POLICY IF EXISTS system_settings_update_admin ON system_settings;
CREATE POLICY system_settings_update_admin ON system_settings FOR UPDATE
    TO authenticated
    USING (public.app_is_admin())
    WITH CHECK (public.app_is_admin());
