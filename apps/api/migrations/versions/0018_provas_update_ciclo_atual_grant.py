"""provas: GRANT UPDATE(ciclo_atual) a authenticated (W3-C15 / Reinicio de Ciclo)

Aditiva e nao destrutiva. O Reinicio de Ciclo (RF-009/RN-006) INCREMENTA
``provas.ciclo_atual`` na MESMA transacao da transicao "Reprovada pelo Vendedor"
-> "Criada" (motor do C11). O privilegio de UPDATE de ``provas`` a
``authenticated`` (= o role de runtime ``rastreio_runtime`` via SET ROLE) e de
COLUNA: a 0015 concedeu apenas ``(status, finalizada_em, updated_at)`` (privilegio
minimo do C11). Sem incluir ``ciclo_atual``, o incremento do C15 falharia com
"permission denied for column" no role NOBYPASSRLS de producao.

Esta migration ADICIONA ``ciclo_atual`` ao grant de coluna (delta sobre a 0015) —
as outras tres permanecem. A RLS de linha NAO muda: ``provas_update_admin``
(``app_is_admin()``) ja escopa a escrita do reinicio (so admin reinicia, conforme
``Autorizacao.ADMIN`` no motor); como os grants de coluna sao do role, o motor e
quem garante que so o reinicio (admin) toca ``ciclo_atual`` — nenhum fluxo
operacional o atualiza. Sem nova POLICY, sem nova tabela.

Espelho versionado em ``migrations/rls/provas_grants.sql`` (atualizado para listar
as 4 colunas — reaplicar apos recriacao da tabela). Idempotente: GRANT/REVOKE de
coluna repetidos nao falham.

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Delta sobre a 0015: acrescenta SO ``ciclo_atual`` ao grant de coluna existente.
_GRANT_CICLO = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT UPDATE (ciclo_atual) ON TABLE provas TO authenticated;
    END IF;
END
$$
"""
_REVOKE_CICLO = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE UPDATE (ciclo_atual) ON TABLE provas FROM authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    op.execute(_GRANT_CICLO)


def downgrade() -> None:
    op.execute(_REVOKE_CICLO)
