-- SELECT de `assinaturas` (W3-C12): espelha o escopo de `provas`.
-- Voce ve a assinatura de uma prova SE ve a prova — o EXISTS roda a RLS de `provas`
-- para o ator (cada perfil herda seu escopo: Vendedor as suas, Motorista as
-- operacionais, 3Studio/Clicheria/Admin todas). Habilita a leitura da assinatura na
-- Timeline (C13). Escopa por `prova_id` (denormalizado), sem depender da
-- movimentacao (inserida DEPOIS — a FK aponta para ca).
-- Idempotente. Reaplicar apos qualquer DROP/recriacao da tabela (CLAUDE.md §9).
DROP POLICY IF EXISTS assinaturas_select_por_prova_visivel ON assinaturas;
CREATE POLICY assinaturas_select_por_prova_visivel ON assinaturas FOR SELECT
    TO authenticated
    USING (EXISTS (SELECT 1 FROM provas p WHERE p.id = assinaturas.prova_id));
