-- UPDATE de `provas` por Motorista (W3-C11): confirmar as travessias (§6.3/§6.5).
-- Espelha o escopo de SELECT AMPLIADO do Motorista (origens + Em Transito): o
-- Motorista atua a partir de `encaminhada_para_laminacao`/`laminacao_concluida`/
-- `de_volta_studio` (USING/origem) e SEMPRE para um estado "Com Motorista"
-- (WITH CHECK/destino, dentro do conjunto). Conjunto de status, sem logica de rota
-- (§11). Idempotente.
DROP POLICY IF EXISTS provas_update_motorista ON provas;
CREATE POLICY provas_update_motorista ON provas FOR UPDATE
    TO authenticated
    USING (
        public.app_setor() = 'motorista'
        AND status IN (
            'encaminhada_para_laminacao',
            'laminacao_concluida',
            'de_volta_studio',
            'com_motorista_ida_laminacao',
            'com_motorista_volta_laminacao',
            'com_motorista_entrega_final'
        )
    )
    WITH CHECK (
        public.app_setor() = 'motorista'
        AND status IN (
            'encaminhada_para_laminacao',
            'laminacao_concluida',
            'de_volta_studio',
            'com_motorista_ida_laminacao',
            'com_motorista_volta_laminacao',
            'com_motorista_entrega_final'
        )
    );
