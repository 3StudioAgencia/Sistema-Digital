"""Repositório SQLAlchemy de assinaturas — log append-only (W3-C12).

Participa da transação do ``SqlAlchemyUnitOfWork`` (mesma ``AsyncSession``); NUNCA
faz commit — a fronteira é do caso de uso (RNF-017), que grava assinatura +
movimentação JUNTAS. A sessão vem de ``abrir_sessao_rls``: o escopo é da RLS
(espelha ``provas``).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.db.models import AssinaturaRow
from src.application.ports.assinaturas_repository import AssinaturasRepositoryPort
from src.domain.assinaturas import Assinatura


def _para_dominio(row: AssinaturaRow) -> Assinatura:
    return Assinatura(
        id=row.id,
        prova_id=row.prova_id,
        ator_id=row.ator_id,
        imagem=bytes(row.imagem),
        content_type=row.content_type,
        created_at=row.created_at,
    )


class SqlAlchemyAssinaturasRepository(AssinaturasRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registrar(self, assinatura: Assinatura) -> Assinatura:
        row = AssinaturaRow(
            id=assinatura.id,
            prova_id=assinatura.prova_id,
            ator_id=assinatura.ator_id,
            imagem=assinatura.imagem,
            content_type=assinatura.content_type,
        )
        self._session.add(row)
        await self._session.flush()
        # eager_defaults: created_at (server default) vem no RETURNING do INSERT.
        assinatura.created_at = row.created_at
        return assinatura

    async def obter(self, assinatura_id: str) -> Assinatura | None:
        row = await self._session.get(AssinaturaRow, assinatura_id)
        return _para_dominio(row) if row is not None else None


__all__ = ["SqlAlchemyAssinaturasRepository"]
