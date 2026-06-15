-- Matriz §7, "Criar Prova": exclusivo do Administrador (flag — ADR-023).
-- WITH CHECK endurecido (migration 0009 — revisão adversarial W2-C06): a
-- camada inferior espelha os INVARIANTES de criação mesmo para acesso direto
-- via Data API/PostgREST, que contorna o backend:
--   - status = 'criada' (US-001 — transições são da máquina de estados, C11);
--   - codigo no formato canônico (DAT §8.3 — mesmo regex de domain/provas.py);
--   - vendedor do setor vendedor e ATIVO (RF-001 — a FK só garante existência;
--     o EXISTS roda sob a RLS de usuarios: o ator é admin, que lê todas).
DROP POLICY IF EXISTS provas_insert_admin ON provas;
CREATE POLICY provas_insert_admin ON provas FOR INSERT
    TO authenticated
    WITH CHECK (
        public.app_is_admin()
        AND status = 'criada'
        AND codigo ~ '^PRV-\d{4}-(0[1-9]|1[0-2])-[2-9A-HJ-KM-NP-Z]{6}$'
        AND EXISTS (
            SELECT 1 FROM usuarios u
            WHERE u.id = vendedor_id AND u.setor = 'vendedor' AND u.ativo
        )
    );
