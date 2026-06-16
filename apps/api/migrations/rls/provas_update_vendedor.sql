-- UPDATE de `provas` por Vendedor (W3-C11): aprovar/reprovar/avancar as PROPRIAS
-- provas (§6). Espelha o escopo de SELECT (so as suas). vendedor_id nao muda numa
-- transicao, entao USING (origem) e WITH CHECK (destino) batem. Idempotente.
DROP POLICY IF EXISTS provas_update_vendedor ON provas;
CREATE POLICY provas_update_vendedor ON provas FOR UPDATE
    TO authenticated
    USING (public.app_setor() = 'vendedor' AND vendedor_id = public.app_current_user_id())
    WITH CHECK (public.app_setor() = 'vendedor' AND vendedor_id = public.app_current_user_id());
