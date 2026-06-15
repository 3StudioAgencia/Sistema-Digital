-- system_settings_select_authenticated.sql — leitura aberta a autenticados (W2-C09 / DP-2)
--
-- O valor das configuracoes (tempo de atraso, template de etiqueta) NAO e
-- sigiloso e alimenta features de TODOS os perfis, lidas server-side na sessao
-- RLS do request: o dashboard (C16, todos os perfis) le `delay_horas_uteis`; a
-- etiqueta (C06, universal-em-escopo — ADR-046) le `etiqueta_template`. Por isso
-- a LEITURA e `authenticated` (USING true) — a ESCRITA continua admin-only
-- (system_settings_{insert,update}_admin). A pagina de gestao segue 3Studio-only
-- pelo proxy (C05) + gate do endpoint (Recurso.CONFIGURACOES).
--
-- Idempotente.
DROP POLICY IF EXISTS system_settings_select_authenticated ON system_settings;
CREATE POLICY system_settings_select_authenticated ON system_settings FOR SELECT
    TO authenticated USING (true);
