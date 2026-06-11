"""usuarios — primeira tabela de dominio + enums (W1-C04)

Cria os tipos ``setor_enum``/``localizacao_enum`` (CREATE TYPE — DAT §2/§4.5),
a tabela ``usuarios`` (PK = UUID de auth.users, vinculo 1:1 — ADR-024), os
indices das colunas de filtro/ordenacao (RNF-019) e habilita RLS com postura
RESTRITIVA provisoria: nenhuma policy para anon/authenticated e privilegios
revogados — acesso ao dado SOMENTE via backend ate o C05 ligar as policies por
perfil (DP-5/ADR-027). O espelho versionado esta em
``migrations/rls/usuarios_baseline_restritiva.sql`` (regra do DAT §2).

Modelo Setor x Administrador: ortogonal (DP-1/ADR-023) — ``administrador`` e um
flag independente do setor; o CHECK bidirecional de localizacao espelha a
RN-009 (obrigatoria para vendedor, indevida para os demais).

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Sincronizados com src/domain/usuarios.py (Setor/Localizacao) — CLAUDE.md §6.
SETORES = ("studio", "vendedor", "motorista", "clicheria")
LOCALIZACOES = ("matriz", "filial")

# Postura RLS provisoria (idempotente) — identica ao .sql versionado em
# migrations/rls/usuarios_baseline_restritiva.sql. Comandos SEPARADOS (asyncpg
# nao aceita multiplos comandos por instrucao preparada); os REVOKE rodam
# condicionados a existencia das roles do Supabase (anon/authenticated nao
# existem no Postgres local de dev/teste).
_RLS_ENABLE = "ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY"
_RLS_REVOKE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE usuarios FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE usuarios FROM authenticated;
    END IF;
END
$$
"""


def upgrade() -> None:
    setor_enum = postgresql.ENUM(*SETORES, name="setor_enum", create_type=False)
    localizacao_enum = postgresql.ENUM(*LOCALIZACOES, name="localizacao_enum", create_type=False)
    setor_enum.create(op.get_bind(), checkfirst=True)
    localizacao_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "usuarios",
        # PK = UUID emitido pelo Supabase Auth (sem default local e sem FK
        # fisica: auth.users e gerenciada fora do Alembic — DAT §2).
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("setor", setor_enum, nullable=False),
        sa.Column("localizacao", localizacao_enum, nullable=True),
        sa.Column(
            "administrador", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        # RN-009 bidirecional: vendedor TEM localizacao; demais NAO tem.
        # (a naming convention do metadata prefixa "ck_usuarios_" sozinha)
        sa.CheckConstraint(
            "(setor = 'vendedor' AND localizacao IS NOT NULL) "
            "OR (setor <> 'vendedor' AND localizacao IS NULL)",
            name="localizacao_por_setor",
        ),
    )

    # Unicidade case-insensitive do e-mail (login e por e-mail no Supabase).
    op.create_index(
        "uq_usuarios_email_lower", "usuarios", [sa.text("lower(email)")], unique=True
    )
    # Colunas de filtro/ordenacao da listagem (RNF-019).
    op.create_index("ix_usuarios_setor", "usuarios", ["setor"])
    op.create_index("ix_usuarios_ativo", "usuarios", ["ativo"])
    op.create_index("ix_usuarios_nome_lower", "usuarios", [sa.text("lower(nome)")])
    op.create_index("ix_usuarios_created_at", "usuarios", ["created_at"])

    op.execute(_RLS_ENABLE)
    op.execute(_RLS_REVOKE)


def downgrade() -> None:
    op.drop_table("usuarios")  # indices e RLS caem junto com a tabela
    op.execute("DROP TYPE IF EXISTS localizacao_enum")
    op.execute("DROP TYPE IF EXISTS setor_enum")
