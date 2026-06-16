-- INSERT de `assinaturas` (W3-C12): defesa em profundidade do comprovante.
-- WITH CHECK: o autor e o proprio ator (`ator_id = app_current_user_id()` — ninguem
-- forja assinatura em nome de outro) E a prova esta no escopo do ator (EXISTS — so
-- assina prova que enxerga). A VALIDADE da transicao (rota/estado/perfil/§6) e do
-- motor no app (`domain/state_machine` — §11); a validade da IMAGEM e do dominio
-- (`validar_assinatura`); aqui a RLS so impede forjar autor/prova fora de escopo.
-- Idempotente.
DROP POLICY IF EXISTS assinaturas_insert_ator_em_escopo ON assinaturas;
CREATE POLICY assinaturas_insert_ator_em_escopo ON assinaturas FOR INSERT
    TO authenticated
    WITH CHECK (
        ator_id = public.app_current_user_id()
        AND EXISTS (SELECT 1 FROM provas p WHERE p.id = assinaturas.prova_id)
    );
