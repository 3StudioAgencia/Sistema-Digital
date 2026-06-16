-- UPDATE de `provas` por 3Studio (W3-C11): transicoes de status (§6). Espelha o
-- escopo de SELECT (ve todas → atualiza todas). USING (linha origem) e WITH CHECK
-- (linha destino) usam o MESMO predicado. O GRANT e so de colunas
-- status/finalizada_em/updated_at (provas_grants.sql); o trigger de rota imutavel
-- (0007) barra mudanca de rota. Idempotente.
DROP POLICY IF EXISTS provas_update_studio ON provas;
CREATE POLICY provas_update_studio ON provas FOR UPDATE
    TO authenticated
    USING (public.app_setor() = 'studio')
    WITH CHECK (public.app_setor() = 'studio');
