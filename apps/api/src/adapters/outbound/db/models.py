"""Modelos SQLAlchemy das tabelas de domínio — espelho do schema do Alembic.

O schema é CRIADO pelas migrations (nunca por ``metadata.create_all`` em
produção — CLAUDE.md §11); estes modelos existem para o ORM mapear linhas ↔
entidades de domínio e para o autogenerate do Alembic comparar estados.

Enums: ``create_type=False`` — os tipos PostgreSQL (``setor_enum``,
``localizacao_enum``) pertencem à migration 0002 (DAT §2/§4.5); o ORM apenas os
referencia. ``values_callable`` persiste o VALOR (lowercase) dos enums Python,
mantendo a sincronização Python ↔ PG do glossário (CLAUDE.md §6).
"""

from datetime import datetime

from sqlalchemy import Boolean, MetaData, String, Uuid, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.domain.usuarios import Localizacao, Setor

# Convenção de nomes determinística: constraints/índices nomeados de forma
# estável entre autogenerate e migrations escritas à mão.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = metadata


def _pg_enum(enum_cls: type[Setor] | type[Localizacao], name: str) -> postgresql.ENUM:
    return postgresql.ENUM(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class UsuarioRow(Base):
    """Linha da tabela ``usuarios`` — PK = UUID de ``auth.users`` (ADR-024).

    Sem FK física para ``auth.users`` (schema gerenciado pelo Supabase, fora do
    Alembic — DAT §2); a integridade do vínculo 1:1 é responsabilidade do
    provisionamento coordenado (``UsuariosService``).
    """

    __tablename__ = "usuarios"
    # RETURNING dos server defaults (created_at/updated_at) no próprio INSERT —
    # o repositório lê os timestamps sem SELECT extra (RNF-020).
    # RUF012 suprimido: idioma do SQLAlchemy — a base declara o atributo como
    # variável de instância, então ClassVar (sugestão do ruff) conflita no mypy.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    setor: Mapped[Setor] = mapped_column(_pg_enum(Setor, "setor_enum"), nullable=False)
    localizacao: Mapped[Localizacao | None] = mapped_column(
        _pg_enum(Localizacao, "localizacao_enum"), nullable=True
    )
    administrador: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


__all__ = ["NAMING_CONVENTION", "Base", "UsuarioRow", "metadata"]
