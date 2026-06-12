"""Unit of Work SQLAlchemy — implementação da porta (movida no W2-C06).

Morava em ``infrastructure/database.py``; movida para cá (W0-A-018/ADR-017):
implementações de porta moram em ``adapters/outbound/``, e a ``infrastructure``
fica com engine/sessões/propagação de RLS (wiring de processo).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.unit_of_work import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Unit of Work por requisição sobre uma ``AsyncSession``.

    A propagação de claims para a RLS (ADR-008) é feita por
    ``propagar_claims_rls`` (listener ``after_begin`` da sessão), e NÃO aqui:
    repositórios fazem leituras que auto-iniciam transações sem passar pelo
    ``begin()``, então o hook de propagação precisa ser por-transação, não
    por-``begin()``. A UoW segue responsável apenas pela fronteira atômica
    (RNF-017).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Exposta para os repositórios concretos (adapters), não para casos de uso."""
        return self._session

    async def begin(self) -> None:
        """Abre a transação explícita do caso de uso (escrita)."""
        if not self._session.in_transaction():
            await self._session.begin()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


__all__ = ["SqlAlchemyUnitOfWork"]
