-- Matriz §7 (◐) + AMPLIACAO W3-C11: o Motorista ve as provas "Em Transito" (os 3
-- contextos "Com Motorista") E as provas nos estados de ORIGEM das suas
-- transicoes (`encaminhada_para_laminacao`, `laminacao_concluida`,
-- `de_volta_studio`) — senao receberia 404 ao escanear a prova que precisa pegar e
-- nunca iniciaria a travessia (§6.3/§6.5). Conjunto de status, sem logica de rota
-- (§11: regra de transicao nao vive no banco). Divergencia da §7 (a listagem do
-- Motorista passa a mostrar tambem "aguardando coleta") registrada em DECISIONS.md.
-- Valores do status_prova_enum (CLAUDE.md §6). Ampliada pela migration 0015.
DROP POLICY IF EXISTS provas_select_motorista ON provas;
CREATE POLICY provas_select_motorista ON provas FOR SELECT
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
    );
