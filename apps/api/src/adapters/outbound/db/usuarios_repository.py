"""Repositório SQLAlchemy de usuários — implementação da porta (W1-C04).

Participa da transação do ``SqlAlchemyUnitOfWork`` (mesma ``AsyncSession``);
NUNCA faz commit — a fronteira transacional é do caso de uso (RNF-017).
"""

from sqlalchemy import ColumnElement, Select, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.models import UsuarioRow
from src.application.ports.usuarios_repository import (
    FiltrosUsuarios,
    PaginaUsuarios,
    UsuariosRepositoryPort,
)
from src.application.usuarios import EmailJaCadastradoError
from src.domain.usuarios import ConflitoDeConcorrenciaError, Usuario


def _para_dominio(row: UsuarioRow) -> Usuario:
    return Usuario(
        id=row.id,
        nome=row.nome,
        email=row.email,
        setor=row.setor,
        localizacao=row.localizacao,
        administrador=row.administrador,
        ativo=row.ativo,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _escapar_like(termo: str) -> str:
    r"""Escapa curingas do LIKE — busca de usuário é literal, nunca padrão."""
    return termo.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


class SqlAlchemyUsuariosRepository(UsuariosRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, usuario_id: str) -> Usuario | None:
        row = await self._session.get(UsuarioRow, usuario_id)
        return _para_dominio(row) if row is not None else None

    async def get_by_email(self, email: str) -> Usuario | None:
        stmt = select(UsuarioRow).where(func.lower(UsuarioRow.email) == email.lower())
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _para_dominio(row) if row is not None else None

    async def add(self, usuario: Usuario) -> None:
        row = UsuarioRow(
            id=usuario.id,
            nome=usuario.nome,
            email=usuario.email,
            setor=usuario.setor,
            localizacao=usuario.localizacao,
            administrador=usuario.administrador,
            ativo=usuario.ativo,
        )
        self._session.add(row)
        # eager_defaults do mapper traz created_at/updated_at no RETURNING do
        # próprio INSERT — sem SELECT extra (RNF-020).
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Corrida de criação (duas requisições passaram pela pré-checagem):
            # a violação do índice único de e-mail é REGRA DE NEGÓCIO (409),
            # não erro interno — o serviço compensa o auth user e propaga.
            if "uq_usuarios_email_lower" in str(exc.orig):
                raise EmailJaCadastradoError() from exc
            raise
        usuario.created_at = row.created_at
        usuario.updated_at = row.updated_at

    async def update(self, usuario: Usuario) -> None:
        # Lock OTIMISTA: o UPDATE só aplica se a linha ainda está na versão
        # (updated_at) lida pelo caso de uso — escrita concorrente perdida vira
        # 409 explícito em vez de ressuscitar campos obsoletos (revisão W1-C04).
        stmt = (
            update(UsuarioRow)
            .where(
                UsuarioRow.id == usuario.id,
                UsuarioRow.updated_at == usuario.updated_at,
            )
            .values(
                nome=usuario.nome,
                setor=usuario.setor,
                localizacao=usuario.localizacao,
                administrador=usuario.administrador,
                ativo=usuario.ativo,
                updated_at=text("clock_timestamp()"),
            )
            .returning(UsuarioRow.updated_at)
        )
        result = await self._session.execute(stmt)
        novo_updated_at = result.scalar_one_or_none()
        if novo_updated_at is None:
            raise ConflitoDeConcorrenciaError()
        usuario.updated_at = novo_updated_at

    async def travar_gestao_de_admins(self) -> None:
        # Advisory lock TRANSACIONAL (liberado no commit/rollback): serializa
        # demoções/desativações de admin para a recontagem da RN-010 ser
        # confiável (fecha o TOCTOU de duas operações concorrentes).
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('usuarios_gestao_admins'))")
        )

    async def listar(self, filtros: FiltrosUsuarios) -> PaginaUsuarios:
        condicoes = self._condicoes(filtros)
        total_stmt = select(func.count()).select_from(UsuarioRow)
        page_stmt: Select[tuple[UsuarioRow]] = select(UsuarioRow)
        for cond in condicoes:
            total_stmt = total_stmt.where(cond)
            page_stmt = page_stmt.where(cond)
        total = (await self._session.execute(total_stmt)).scalar_one()
        page_stmt = (
            page_stmt.order_by(func.lower(UsuarioRow.nome), UsuarioRow.id)
            .offset((filtros.page - 1) * filtros.page_size)
            .limit(filtros.page_size)
        )
        rows = (await self._session.execute(page_stmt)).scalars().all()
        return PaginaUsuarios(
            items=[_para_dominio(r) for r in rows],
            total=total,
            page=filtros.page,
            page_size=filtros.page_size,
        )

    async def count_admins_ativos(self, excluir_id: str | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(UsuarioRow)
            .where(UsuarioRow.administrador.is_(True), UsuarioRow.ativo.is_(True))
        )
        if excluir_id is not None:
            stmt = stmt.where(UsuarioRow.id != excluir_id)
        return (await self._session.execute(stmt)).scalar_one()

    @staticmethod
    def _condicoes(filtros: FiltrosUsuarios) -> list[ColumnElement[bool]]:
        condicoes: list[ColumnElement[bool]] = []
        if filtros.busca:
            padrao = f"%{_escapar_like(filtros.busca)}%"
            condicoes.append(
                UsuarioRow.nome.ilike(padrao, escape="\\")
                | UsuarioRow.email.ilike(padrao, escape="\\")
            )
        if filtros.setor is not None:
            condicoes.append(UsuarioRow.setor == filtros.setor)
        if filtros.ativo is not None:
            condicoes.append(UsuarioRow.ativo.is_(filtros.ativo))
        return condicoes


__all__ = ["SqlAlchemyUsuariosRepository"]
