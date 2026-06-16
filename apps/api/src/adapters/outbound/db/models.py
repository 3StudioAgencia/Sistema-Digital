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
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, MetaData, String, Text, Uuid, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.domain.provas import EstadoProva, Rota
from src.domain.state_machine.enums import Acao
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


def _pg_enum(enum_cls: type[StrEnum], name: str) -> postgresql.ENUM:
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


class ProvaRow(Base):
    """Linha da tabela ``provas`` (migration 0007 — W2-C06).

    ``id`` é gerado pela APLICAÇÃO (uuid4) — o ``server_default`` existe só
    como rede de segurança. ``rota`` não tem caminho de update em nenhum
    repositório (RN-007); o trigger ``trg_provas_rota_imutavel`` rejeita
    qualquer tentativa direta no banco.
    """

    __tablename__ = "provas"
    # RETURNING dos server defaults (created_at/updated_at) no próprio INSERT —
    # mesmo princípio do UsuarioRow (RNF-020).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    codigo: Mapped[str] = mapped_column(String(18), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    requerimento: Mapped[str] = mapped_column(String(50), nullable=False)
    cliente: Mapped[str] = mapped_column(String(200), nullable=False)
    vendedor_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("usuarios.id"), nullable=False
    )
    rota: Mapped[Rota] = mapped_column(_pg_enum(Rota, "rota_enum"), nullable=False)
    status: Mapped[EstadoProva] = mapped_column(
        _pg_enum(EstadoProva, "status_prova_enum"),
        nullable=False,
        server_default=text("'criada'"),
    )
    # Ciclo de revisão (migration 0012 — W2-C08/DP-1): nasce 1 (server default) e
    # é incrementado pelo C15. eager_defaults traz o valor no RETURNING do INSERT.
    ciclo_atual: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    arte_key: Mapped[str] = mapped_column(String(255), nullable=False)
    arte_content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # Carimbo terminal (migration 0010 — W2-C07): NULL até o C11 popular nas
    # transições terminais; alimenta o filtro "Finalizada em" da listagem.
    finalizada_em: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )


class SystemSettingRow(Base):
    """Linha da tabela ``system_settings`` (migration 0013 — W2-C09).

    Modelo chave-valor (DP-1): ``value`` JSONB guarda o valor da chave conhecida
    (escalar como ``delay_horas_uteis`` ou objeto como ``etiqueta_template``),
    validado pelo registro de domínio (``src/domain/settings.py``). RLS: leitura
    ``authenticated``, escrita admin-only (DP-2/DP-3). ``updated_by`` é o UUID do
    admin que salvou (auditoria leve — sem FK, ``usuarios`` nunca é deletado).
    """

    __tablename__ = "system_settings"
    # RETURNING do updated_at (server default) no upsert — sem SELECT extra (RNF-020).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(postgresql.JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)


class RateLimitContadorRow(Base):
    """Linha da tabela ``rate_limit_contadores`` (migration 0014 — W3-C10).

    Contador de tentativas por ator: UMA linha por ``(user_id, chave)``. O
    limitador (``SqlAlchemyRateLimiter``) faz upsert atômico em SQL puro
    (``app_current_user_id()`` + ``date_trunc``) que incrementa na janela de 1 min
    e RESETA ao virar o minuto — sem job de limpeza. RLS ``rate_limit_contadores_self``:
    o ator só toca a PRÓPRIA linha. Este modelo existe para o espelho de schema
    (autogenerate do Alembic); não é mapeado em leituras de runtime.
    """

    __tablename__ = "rate_limit_contadores"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    janela_inicio: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False
    )
    contador: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class MovimentacaoRow(Base):
    """Linha da tabela ``movimentacoes`` (migration 0015 — W3-C11).

    Log APPEND-ONLY do fluxo (RNF-006/DP-3): UMA linha por transição. Imutável —
    o trigger ``trg_movimentacoes_append_only`` bloqueia UPDATE/DELETE e não há
    GRANT para eles. ``idempotency_key`` é UNIQUE (RNF-015): reenvio da mesma
    transição converge, não duplica. ``assinatura_ref`` é nullable (DP-1): o C12
    adiciona a tabela ``signatures`` + a FK. ``acao`` usa ``acao_enum``
    (sincronizado com ``domain/state_machine/enums.py`` — DAT §4.5).
    """

    __tablename__ = "movimentacoes"
    # RETURNING de id/created_at (server defaults) no próprio INSERT (RNF-020).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    prova_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("provas.id"), nullable=False
    )
    estado_origem: Mapped[EstadoProva] = mapped_column(
        _pg_enum(EstadoProva, "status_prova_enum"), nullable=False
    )
    estado_destino: Mapped[EstadoProva] = mapped_column(
        _pg_enum(EstadoProva, "status_prova_enum"), nullable=False
    )
    acao: Mapped[Acao] = mapped_column(_pg_enum(Acao, "acao_enum"), nullable=False)
    ator_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    ciclo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    assinatura_ref: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


__all__ = [
    "NAMING_CONVENTION",
    "Base",
    "MovimentacaoRow",
    "ProvaRow",
    "RateLimitContadorRow",
    "SystemSettingRow",
    "UsuarioRow",
    "metadata",
]
