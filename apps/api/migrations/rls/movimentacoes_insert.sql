-- INSERT de `movimentacoes` (W3-C11): defesa em profundidade do registro de
-- transicao. WITH CHECK: o autor e o proprio ator (`ator_id =
-- app_current_user_id()` — ninguem forja movimentacao em nome de outro) E a prova
-- esta no escopo do ator (EXISTS — so registra movimento de prova que enxerga).
-- A VALIDADE da transicao (rota/estado/perfil/§6) e do motor no app
-- (`domain/state_machine` — §11: regra de transicao NUNCA vive no banco); aqui a
-- RLS so impede forjar autor/prova fora de escopo. Idempotente.
DROP POLICY IF EXISTS movimentacoes_insert_ator_em_escopo ON movimentacoes;
CREATE POLICY movimentacoes_insert_ator_em_escopo ON movimentacoes FOR INSERT
    TO authenticated
    WITH CHECK (
        ator_id = public.app_current_user_id()
        AND EXISTS (SELECT 1 FROM provas p WHERE p.id = movimentacoes.prova_id)
    );
