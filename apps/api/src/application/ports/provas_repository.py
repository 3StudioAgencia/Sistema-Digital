"""Porta do repositório de provas — persistência da tabela de domínio (W2-C06).

O C06 só precisa de criação e leitura pontual (a listagem paginada é do C07,
que estende esta porta). Escritas participam da transação corrente do
``UnitOfWork`` — o commit é do caso de uso, nunca do repositório (RNF-017).
"""

from abc import ABC, abstractmethod

from src.domain.provas import Prova


class CodigoJaExisteError(Exception):
    """Colisão da constraint ``uq_provas_codigo`` — sinal de RETRY do serviço
    (DP-3), não erro de negócio: o cliente nunca escolhe o código."""


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


__all__ = ["CodigoJaExisteError", "ProvasRepositoryPort"]
