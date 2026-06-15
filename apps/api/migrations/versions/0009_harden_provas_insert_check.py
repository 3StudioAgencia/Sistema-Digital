"""Endurece o WITH CHECK de provas_insert_admin (revisao adversarial W2-C06)

A policy original (0008) checava apenas o flag admin. Como `provas` vive no
schema `public` (exposto pela Data API/PostgREST do Supabase), um admin podia
inserir DIRETO no banco linhas que contornam todas as validacoes de dominio do
backend: prova nascendo em status arbitrario (burlando a maquina de estados,
que vive so em codigo — CLAUDE.md §5.3), codigo fora do contrato do C10/QR e
vendedor de outro setor/inativo (a FK so garante existencia).

A camada inferior do RBAC passa a espelhar os INVARIANTES de criacao:
- status = 'criada' (US-001: toda prova nasce "Criada");
- codigo no formato canonico PRV-AAAA-MM-NNNNNN com charset nao ambiguo
  (DAT §8.3 — mesmo regex de domain/provas.py);
- vendedor_id aponta para usuario do setor vendedor ATIVO (RF-001; o EXISTS
  roda sob a RLS de usuarios — o ator e admin, que le todas as linhas).

Espelho 1:1 atualizado em migrations/rls/provas_insert_admin.sql.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mesmo charset de domain/provas.py (CODIGO_ALFABETO sem 0/O, 1/I/L).
_POLICY_ENDURECIDA = (
    "CREATE POLICY provas_insert_admin ON provas FOR INSERT "
    "TO authenticated WITH CHECK ("
    "public.app_is_admin() "
    "AND status = 'criada' "
    r"AND codigo ~ '^PRV-\d{4}-(0[1-9]|1[0-2])-[2-9A-HJ-KM-NP-Z]{6}$' "
    "AND EXISTS (SELECT 1 FROM usuarios u WHERE u.id = vendedor_id "
    "AND u.setor = 'vendedor' AND u.ativo)"
    ")"
)

# Versao da 0008 (so o flag) — restaurada no downgrade.
_POLICY_ORIGINAL = (
    "CREATE POLICY provas_insert_admin ON provas FOR INSERT "
    "TO authenticated WITH CHECK (public.app_is_admin())"
)


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS provas_insert_admin ON provas")
    op.execute(_POLICY_ENDURECIDA)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS provas_insert_admin ON provas")
    op.execute(_POLICY_ORIGINAL)
