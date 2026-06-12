-- Matriz §7 (◐): Motorista vê APENAS provas "Em Trânsito" — qualquer um dos
-- TRÊS contextos "Com Motorista" da v1.0 (ida laminação, volta laminação,
-- entrega final). Valores do status_prova_enum (CLAUDE.md §6).
DROP POLICY IF EXISTS provas_select_motorista ON provas;
CREATE POLICY provas_select_motorista ON provas FOR SELECT
    TO authenticated
    USING (
        public.app_setor() = 'motorista'
        AND status IN (
            'com_motorista_ida_laminacao',
            'com_motorista_volta_laminacao',
            'com_motorista_entrega_final'
        )
    );
