-- SELECT de `audit_log` (W6-C20): EXCLUSIVO do 3Studio (admin).
-- Matriz §7, "Log de Auditoria" ●○○○ — chaveia pelo FLAG `administrador` (ADR-023),
-- igual a Relatorios/Configuracoes. A pagina de Auditoria (C20) e gateada na rota
-- (proxy + sidebar) E no endpoint (Recurso.LOG_AUDITORIA); esta policy e a camada
-- inferior (defesa em profundidade): mesmo chamando direto, so admin le o log.
-- A funcao de verificacao de integridade (SECURITY INVOKER) tambem so enxerga
-- TODAS as linhas porque o chamador e admin. Idempotente.
DROP POLICY IF EXISTS audit_log_select_admin ON audit_log;
CREATE POLICY audit_log_select_admin ON audit_log
    FOR SELECT
    TO authenticated
    USING (public.app_is_admin());
