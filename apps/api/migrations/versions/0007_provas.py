"""provas — primeira tabela de dominio de provas + enums do fluxo (W2-C06)

Cria os tipos ``rota_enum`` (NOT NULL desde a primeira migration — RN-007,
CLAUDE.md §2.1) e ``status_prova_enum`` COMPLETO (os 14 estados da Requisitos
v1.0 §6 — DP-4: nasce tipado correto e evita ALTER TYPE no C11), a tabela
``provas`` (codigo unico do identificador PRV-AAAA-MM-NNNNNN, FK
``vendedor_id`` -> ``usuarios``, arte no R2 por key), os indices das colunas de
filtro/ordenacao (RNF-019: status, rota, vendedor_id, created_at) e o trigger
``BEFORE UPDATE`` que torna a rota IMUTAVEL no banco (RN-007/DP-5 — uma CHECK
nao compara OLD/NEW, por isso trigger).

RLS: habilitada com postura RESTRITIVA provisoria (mesmo padrao do 0002) —
nenhuma policy e privilegios revogados; a migration 0008 liga as policies por
perfil (DP-6) espelhadas em ``migrations/rls/provas_*.sql``.

As transicoes de estado NAO moram aqui nem no banco: vivem em
``domain/state_machine/rules.py`` (C11 — CLAUDE.md §5.3). O C06 so cria a prova
no estado inicial ``criada``.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Sincronizados com src/domain/provas.py (Rota/EstadoProva) — CLAUDE.md §6.
ROTAS = ("matriz", "lam_matriz", "filial", "lam_filial")
ESTADOS = (
    "criada",
    "encaminhada_para_laminacao",
    "com_motorista_ida_laminacao",
    "laminacao_concluida",
    "com_motorista_volta_laminacao",
    "de_volta_studio_pos_laminacao",
    "retirada_vendedor",
    "encaminhada_para_vendedor",
    "aprovada_vendedor",
    "reprovada_vendedor",
    "de_volta_studio",
    "com_motorista_entrega_final",
    "recebida_clicheria",
    "cancelada",
)

# Imutabilidade da rota no BANCO (RN-007/DP-5): trigger BEFORE UPDATE OF rota —
# dispara apenas quando a coluna aparece no SET; IS DISTINCT FROM mantem o
# UPDATE idempotente (SET rota = rota) valido. ``SET search_path = ''`` pelo
# mesmo motivo dos helpers de RLS (W1-A-004). ERRCODE de check_violation: a
# violacao chega a aplicacao como erro de integridade, nao como erro generico.
_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION public.provas_rota_imutavel()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    IF NEW.rota IS DISTINCT FROM OLD.rota THEN
        RAISE EXCEPTION 'rota e imutavel apos a criacao da prova (RN-007)'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$
"""

_TRIGGER = """
CREATE TRIGGER trg_provas_rota_imutavel
BEFORE UPDATE OF rota ON provas
FOR EACH ROW EXECUTE FUNCTION public.provas_rota_imutavel()
"""

# Postura RLS provisoria (idempotente), SUPERSEDIDA pela 0008 — mesmo padrao e
# motivos do 0002 (REVOKE condicionado a existencia das roles do Supabase).
_RLS_ENABLE = "ALTER TABLE provas ENABLE ROW LEVEL SECURITY"
_RLS_REVOKE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE provas FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE provas FROM authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    rota_enum = postgresql.ENUM(*ROTAS, name="rota_enum", create_type=False)
    status_enum = postgresql.ENUM(*ESTADOS, name="status_prova_enum", create_type=False)
    rota_enum.create(op.get_bind(), checkfirst=True)
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "provas",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Identificador PRV-AAAA-MM-NNNNNN (DP-3): 18 chars fixos; e o MESMO
        # conteudo do QR Code (DAT §8.3). UNIQUE + retry de colisao no servico.
        sa.Column("codigo", sa.String(length=18), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        # Numero do requerimento como TEXTO (preserva zeros a esquerda);
        # a validacao de digitos e da borda Pydantic (RF-001).
        sa.Column("requerimento", sa.String(length=50), nullable=False),
        sa.Column("cliente", sa.String(length=200), nullable=False),
        # FK -> usuarios (setor Vendedor ativo — validado na aplicacao; a FK
        # garante a existencia, nao o setor). Sem ON DELETE: usuarios nunca sao
        # deletados (apenas desativados — US-015).
        sa.Column(
            "vendedor_id",
            sa.Uuid(as_uuid=False),
            sa.ForeignKey("usuarios.id", name="fk_provas_vendedor_id_usuarios"),
            nullable=False,
        ),
        # Rota escolhida MANUALMENTE pelo admin na criacao (RN-007) — NOT NULL
        # desde a primeira migration e imutavel (trigger abaixo).
        sa.Column("rota", rota_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default=sa.text("'criada'")),
        # Arte no R2 (C01): key do objeto + content-type validado (JPG/PNG).
        sa.Column("arte_key", sa.String(length=255), nullable=False),
        sa.Column("arte_content_type", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("codigo", name="uq_provas_codigo"),
    )

    # Colunas de filtro/ordenacao da listagem e do dashboard (RNF-019,
    # antecipando o C07): status, rota, vendedor_id, created_at.
    op.create_index("ix_provas_status", "provas", ["status"])
    op.create_index("ix_provas_rota", "provas", ["rota"])
    op.create_index("ix_provas_vendedor_id", "provas", ["vendedor_id"])
    op.create_index("ix_provas_created_at", "provas", ["created_at"])

    op.execute(_TRIGGER_FUNCTION)
    op.execute(_TRIGGER)

    op.execute(_RLS_ENABLE)
    op.execute(_RLS_REVOKE)


def downgrade() -> None:
    op.drop_table("provas")  # indices, trigger e RLS caem junto com a tabela
    op.execute("DROP FUNCTION IF EXISTS public.provas_rota_imutavel()")
    op.execute("DROP TYPE IF EXISTS status_prova_enum")
    op.execute("DROP TYPE IF EXISTS rota_enum")
