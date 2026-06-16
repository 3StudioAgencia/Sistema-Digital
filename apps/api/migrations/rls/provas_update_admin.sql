-- UPDATE de `provas` por Admin (W3-C11): habilita Cancelar/Reiniciar (acoes
-- "Exclusivo 3Studio" — flag administrador, ADR-023) de qualquer setor. Espelha o
-- escopo de SELECT do admin (ve todas). A autorizacao FINA da acao (so admin pode
-- Cancelar/Reiniciar) e do motor no app; aqui a RLS so garante o escopo de dado.
-- Idempotente.
DROP POLICY IF EXISTS provas_update_admin ON provas;
CREATE POLICY provas_update_admin ON provas FOR UPDATE
    TO authenticated
    USING (public.app_is_admin())
    WITH CHECK (public.app_is_admin());
