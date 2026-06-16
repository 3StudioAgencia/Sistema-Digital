-- SELECT de `movimentacoes` (W3-C11/DP-3): espelha o escopo de `provas`.
-- Voce ve as movimentacoes de uma prova SE ve a prova — o EXISTS roda a RLS de
-- `provas` para o ator (cada perfil herda seu escopo: Vendedor as suas, Motorista
-- as operacionais, 3Studio/Clicheria/Admin todas). Isso habilita a Timeline (C13)
-- para perfis em escopo; o "log completo de TODAS as provas" so e visivel a quem
-- ve todas (RNF-006 — a pagina Log de Auditoria do C20 e 3Studio-only na rota).
-- Idempotente. Reaplicar apos qualquer DROP/recriacao da tabela (CLAUDE.md §9).
DROP POLICY IF EXISTS movimentacoes_select_por_prova_visivel ON movimentacoes;
CREATE POLICY movimentacoes_select_por_prova_visivel ON movimentacoes FOR SELECT
    TO authenticated
    USING (EXISTS (SELECT 1 FROM provas p WHERE p.id = movimentacoes.prova_id));
