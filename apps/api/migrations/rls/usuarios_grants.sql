-- usuarios_grants.sql — privilegios de tabela definitivos (W1-C05 / ADR-032)
--
-- Substitui a postura RESTRITIVA provisoria do C04 (REVOKE total de
-- authenticated, dado so via owner): a partir do C05 a RLS por perfil (policies
-- nesta pasta) e quem filtra. authenticated recebe privilegios de tabela e a
-- defesa em profundidade real passa a valer (DP-6 / opcao 6-A) — inclusive
-- sobre o caminho do backend, que serve usuarios via SET ROLE authenticated +
-- claims propagados (ADR-008). "anon" continua sem qualquer acesso.
--
-- Idempotente; condicionado a existencia das roles (criadas por _roles.sql).
-- Pre-requisito: RLS ja habilitada na tabela (migration 0002).

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE usuarios FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE usuarios TO authenticated;
    END IF;
END
$$;
