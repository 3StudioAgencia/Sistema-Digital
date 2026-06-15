-- system_settings_insert_admin.sql — escrita inicial exclusiva do admin (W2-C09 / DP-3)
--
-- Matriz §7 "Configuracoes" = Exclusivo 3Studio (flag administrador — ADR-023).
-- O INSERT do upsert (INSERT ... ON CONFLICT DO UPDATE) corre no backend sob
-- SET ROLE authenticated + claims do admin (ADR-008): o WITH CHECK garante que so
-- um admin grava, na camada do banco (defesa em profundidade — espelha
-- usuarios_insert_admin / provas_insert_admin).
--
-- Idempotente.
DROP POLICY IF EXISTS system_settings_insert_admin ON system_settings;
CREATE POLICY system_settings_insert_admin ON system_settings FOR INSERT
    TO authenticated WITH CHECK (public.app_is_admin());
