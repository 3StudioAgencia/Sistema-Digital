"""Porta do repositório de provas — persistência da tabela de domínio (W2-C06).

O C06 criou a criação e a leitura pontual; o **C07 estende** esta porta com a
listagem paginada (busca + filtros combináveis), os vendedores em escopo (para o
dropdown) e a projeção de nomes de vendedor (``nomes_de_vendedores`` — DP-7).
Escritas participam da transação corrente do ``UnitOfWork`` — o commit é do caso
de uso, nunca do repositório (RNF-017).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import date

from src.domain.provas import EstadoProva, Prova, Rota

# Limites de paginação server-side (RNF-019) — alinhados ao C04 (usuarios).
PAGE_SIZE_PADRAO = 20
PAGE_SIZE_MAXIMO = 100


@dataclass(frozen=True)
class FiltrosProvas:
    """Filtros da listagem (espelham a barra do design — RF-013/RF-014/US-012).

    Datas são ``date`` (input nativo): a borda HTTP recebe ``YYYY-MM-DD`` e o
    repositório aplica os limites de dia. Filtros combináveis (AND); ``busca``
    cobre nome E requerimento; ``cliente`` é "contém". O ESCOPO por perfil NÃO
    está aqui — é da RLS de ``provas`` (C06).
    """

    busca: str | None = None
    cliente: str | None = None
    status: EstadoProva | None = None
    rota: Rota | None = None
    vendedor_id: str | None = None
    criada_de: date | None = None
    criada_ate: date | None = None
    finalizada_de: date | None = None
    finalizada_ate: date | None = None
    page: int = 1
    page_size: int = PAGE_SIZE_PADRAO

    def saneados(self) -> "FiltrosProvas":
        """Clampa a paginação (RNF-019) e normaliza os textos de busca."""
        page = max(1, self.page)
        page_size = min(max(1, self.page_size), PAGE_SIZE_MAXIMO)
        busca = self.busca.strip() if self.busca and self.busca.strip() else None
        cliente = self.cliente.strip() if self.cliente and self.cliente.strip() else None
        return replace(self, busca=busca, cliente=cliente, page=page, page_size=page_size)


@dataclass(frozen=True)
class PaginaProvas:
    items: list[Prova]
    total: int
    page: int
    page_size: int


class CodigoJaExisteError(Exception):
    """Colisão da constraint ``uq_provas_codigo`` — sinal de RETRY do serviço
    (DP-3), não erro de negócio: o cliente nunca escolhe o código."""


class ProvaJaExisteError(Exception):
    """Violação da PK de ``provas`` — o ``prova_id`` (chave de idempotência,
    RNF-015) já foi persistido: uma requisição idêntica venceu a corrida. O
    serviço CONVERGE para a prova existente em vez de duplicar."""


class ProvasRepositoryPort(ABC):
    """Operações de persistência da entidade ``Prova``."""

    @abstractmethod
    async def add(self, prova: Prova) -> None:
        """Insere a prova na transação corrente (flush, sem commit).

        Preenche ``created_at``/``updated_at``/``status`` a partir do RETURNING.
        Levanta ``CodigoJaExisteError`` na colisão do código único.
        """

    @abstractmethod
    async def get(self, prova_id: str) -> Prova | None:
        """Busca pontual por id — o escopo é da RLS (sessão com claims)."""

    @abstractmethod
    async def listar(self, filtros: FiltrosProvas) -> PaginaProvas:
        """Página de provas (busca + filtros), ordenada por ``created_at`` desc.

        Consulta ÚNICA e eficiente (sem N+1): contagem + página na mesma sessão,
        usando os índices do C06 (RNF-019). O ESCOPO por perfil é da RLS.
        """

    @abstractmethod
    async def vendedor_ids_distintos(self) -> list[str]:
        """Vendedores DISTINTOS presentes nas provas VISÍVEIS ao ator (RLS).

        Alimenta o dropdown de filtro "Vendedor" sem vazar escopo: para 3Studio/
        Clicheria/Admin = todos os vendedores com provas; para Vendedor = só ele.
        """

    @abstractmethod
    async def nomes_de_vendedores(self, ids: list[str]) -> dict[str, str]:
        """Mapa ``vendedor_id -> nome`` via ``public.nomes_de_vendedores`` (DP-7).

        Função SECURITY DEFINER que projeta só id+nome de vendedores — resolve o
        nome para perfis que a RLS de ``usuarios`` não deixaria ler (3Studio/
        Clicheria não-admin, Motorista), sem ampliar a Matriz §7.
        """


__all__ = [
    "PAGE_SIZE_MAXIMO",
    "PAGE_SIZE_PADRAO",
    "CodigoJaExisteError",
    "FiltrosProvas",
    "PaginaProvas",
    "ProvaJaExisteError",
    "ProvasRepositoryPort",
]
