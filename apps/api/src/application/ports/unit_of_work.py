"""Porta de Unit of Work — fronteira transacional por requisição.

Nesta wave (C01) a porta é apenas o esqueleto da fronteira transacional: ainda
não há repositórios de domínio para pendurar nela. Ela existe desde já para que
a propagação de claims/RLS por request (ADR-008, Wave 1/C05) caiba SEM
refatoração estrutural. A implementação concreta vive em
``src/adapters/outbound/db/unit_of_work.py`` (SqlAlchemyUnitOfWork — W0-A-018).
"""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


class UnitOfWork(ABC):
    """Delimita uma transação atômica de negócio (RNF-017).

    Uso previsto nos casos de uso::

        async with uow:
            ...  # operações via repositórios
            await uow.commit()

    Sair do bloco sem ``commit()`` faz rollback — falha parcial nunca persiste.
    """

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.rollback()

    @abstractmethod
    async def commit(self) -> None:
        """Confirma a transação corrente."""

    @abstractmethod
    async def rollback(self) -> None:
        """Desfaz a transação corrente (no-op se nada pendente)."""
