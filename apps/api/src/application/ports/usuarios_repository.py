"""Porta do repositório de usuários — persistência da tabela de domínio (W1-C04).

A listagem é SEMPRE paginada server-side com filtros indexados (RNF-019) e a
contagem vem na mesma ida lógica ao banco (duas queries na mesma sessão — sem
N+1, RNF-022).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.usuarios import Setor, Usuario

PAGE_SIZE_PADRAO = 20
PAGE_SIZE_MAXIMO = 100


@dataclass(frozen=True)
class FiltrosUsuarios:
    """Filtros da listagem (espelham a UI: busca, setor, status)."""

    busca: str | None = None
    setor: Setor | None = None
    ativo: bool | None = None
    page: int = 1
    page_size: int = PAGE_SIZE_PADRAO

    def saneados(self) -> "FiltrosUsuarios":
        """Clampa paginação a limites seguros (RNF-019: limite máximo por página)."""
        page = max(1, self.page)
        page_size = min(max(1, self.page_size), PAGE_SIZE_MAXIMO)
        busca = self.busca.strip() if self.busca and self.busca.strip() else None
        return FiltrosUsuarios(
            busca=busca, setor=self.setor, ativo=self.ativo, page=page, page_size=page_size
        )


@dataclass(frozen=True)
class PaginaUsuarios:
    items: list[Usuario]
    total: int
    page: int
    page_size: int


class UsuariosRepositoryPort(ABC):
    """Operações de persistência da entidade ``Usuario``.

    Escritas participam da transação corrente do ``UnitOfWork`` — o commit é do
    caso de uso, nunca do repositório (RNF-017).
    """

    @abstractmethod
    async def get(self, usuario_id: str) -> Usuario | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Usuario | None: ...

    @abstractmethod
    async def add(self, usuario: Usuario) -> None: ...

    @abstractmethod
    async def update(self, usuario: Usuario) -> None: ...

    @abstractmethod
    async def listar(self, filtros: FiltrosUsuarios) -> PaginaUsuarios: ...

    @abstractmethod
    async def count_admins_ativos(self, excluir_id: str | None = None) -> int:
        """Quantos administradores ATIVOS existem (salvaguarda do último admin)."""


__all__ = [
    "PAGE_SIZE_MAXIMO",
    "PAGE_SIZE_PADRAO",
    "FiltrosUsuarios",
    "PaginaUsuarios",
    "UsuariosRepositoryPort",
]
