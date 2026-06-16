-- UPDATE de `provas` por Clicheria (W3-C11): transicoes de status (§6). Espelha o
-- escopo de SELECT (ve todas → atualiza todas). Idempotente.
DROP POLICY IF EXISTS provas_update_clicheria ON provas;
CREATE POLICY provas_update_clicheria ON provas FOR UPDATE
    TO authenticated
    USING (public.app_setor() = 'clicheria')
    WITH CHECK (public.app_setor() = 'clicheria');
