"""assinaturas — comprovante imutavel de cada movimentacao + FK do C11 (W3-C12)

Fecha o laco do fluxo de movimentacao (identificar -> assinar -> confirmar ->
transicao). RN-003: cada transicao da maquina de estados (C11) e comprovada por uma
assinatura DESENHADA (react-signature-canvas -> PNG). Cria:

1. ``assinaturas`` — bytea (DP-2): a imagem nasce na MESMA transacao da movimentacao
   (RNF-017/DP-1), entao nada externo (R2) a sincronizar — sem assinatura orfa num
   rollback. APPEND-ONLY (RN-003/RNF-006): trigger ``assinaturas_append_only``
   (bloqueia UPDATE/DELETE ate para o owner) + ausencia de GRANT UPDATE/DELETE.
   ``prova_id``/``ator_id`` denormalizados: a RLS se escopa SEM depender da
   movimentacao (inserida DEPOIS — a FK aponta para ca). RLS:
   - SELECT: quem enxerga a prova (espelha ``provas`` via EXISTS) — habilita a
     leitura da assinatura na Timeline (C13);
   - INSERT: WITH CHECK ``ator_id = app_current_user_id()`` (nao forja assinatura
     de outro) E a prova no escopo do ator (EXISTS).
2. FK ``movimentacoes.assinatura_ref -> assinaturas.id`` (DP-1): a coluna nasceu
   nullable e SEM FK no C11 (0015), deixada para o C12 fechar. Mantida NULLABLE —
   Cancelar/Reiniciar (C14/C15) podem nao capturar um traco; so o fluxo de
   assinatura cria a linha.

Espelhos 1:1 em ``migrations/rls/assinaturas_*.sql``. Instrucoes SEPARADAS (asyncpg
nao aceita multiplos comandos por instrucao — mesmo motivo do 0008/0013/0014/0015).

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- imutabilidade: trigger append-only (espelha o padrao do 0015) ----------
_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION public.assinaturas_append_only()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    RAISE EXCEPTION 'assinaturas e append-only (RN-003): % nao e permitido', TG_OP
        USING ERRCODE = 'check_violation';
END;
$$
"""
_TRIGGER = """
CREATE TRIGGER trg_assinaturas_append_only
BEFORE UPDATE OR DELETE ON assinaturas
FOR EACH ROW EXECUTE FUNCTION public.assinaturas_append_only()
"""

# --- assinaturas: RLS (espelhos: assinaturas_*.sql) -------------------------
_RLS_ENABLE = "ALTER TABLE assinaturas ENABLE ROW LEVEL SECURITY"
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE assinaturas FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE assinaturas FROM authenticated;
        GRANT SELECT, INSERT ON TABLE assinaturas TO authenticated;
    END IF;
END
$$
"""
_SELECT_NOME = "assinaturas_select_por_prova_visivel"
_SELECT = (
    "CREATE POLICY assinaturas_select_por_prova_visivel ON assinaturas FOR SELECT "
    "TO authenticated "
    "USING (EXISTS (SELECT 1 FROM provas p WHERE p.id = assinaturas.prova_id))"
)
_INSERT_NOME = "assinaturas_insert_ator_em_escopo"
_INSERT = (
    "CREATE POLICY assinaturas_insert_ator_em_escopo ON assinaturas FOR INSERT "
    "TO authenticated "
    "WITH CHECK ("
    "  ator_id = public.app_current_user_id()"
    "  AND EXISTS (SELECT 1 FROM provas p WHERE p.id = assinaturas.prova_id)"
    ")"
)

# --- FK do C11 (movimentacoes.assinatura_ref -> assinaturas.id) -------------
_FK_NOME = "fk_movimentacoes_assinatura_ref_assinaturas"


def upgrade() -> None:
    op.create_table(
        "assinaturas",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "prova_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("provas.id", name="fk_assinaturas_prova_id_provas"),
            nullable=False,
        ),
        # Ator que desenhou a assinatura (= sub/user_id do JWT). Sem FK para
        # usuarios (mesma filosofia de movimentacoes: usuarios nunca e deletado).
        sa.Column("ator_id", sa.Uuid(as_uuid=False), nullable=False),
        # Imagem do canvas (PNG/JPEG) — bytea: nasce na transacao da movimentacao.
        sa.Column("imagem", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Leitura por prova (Timeline C13 + escopo da RLS via EXISTS).
    op.create_index("ix_assinaturas_prova_id", "assinaturas", ["prova_id"])

    op.execute(_TRIGGER_FUNCTION)
    op.execute(_TRIGGER)

    op.execute(_RLS_ENABLE)
    op.execute(_GRANTS)
    op.execute(f"DROP POLICY IF EXISTS {_SELECT_NOME} ON assinaturas")
    op.execute(_SELECT)
    op.execute(f"DROP POLICY IF EXISTS {_INSERT_NOME} ON assinaturas")
    op.execute(_INSERT)

    # Fecha o contrato do C11: a referencia da assinatura vira FK (DP-1).
    op.create_foreign_key(_FK_NOME, "movimentacoes", "assinaturas", ["assinatura_ref"], ["id"])


def downgrade() -> None:
    op.drop_constraint(_FK_NOME, "movimentacoes", type_="foreignkey")
    op.drop_table("assinaturas")  # indice, trigger e RLS caem junto
    op.execute("DROP FUNCTION IF EXISTS public.assinaturas_append_only()")
