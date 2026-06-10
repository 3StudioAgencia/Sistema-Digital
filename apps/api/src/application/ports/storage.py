"""Porta de storage de objetos (artes das provas).

A porta é SÍNCRONA por decisão deliberada: o SDK concreto (boto3) é síncrono e
os handlers async chamam a porta via threadpool (``run_in_threadpool``), o que
mantém o event loop livre sem acoplar a interface a um SDK específico.
"""

from abc import ABC, abstractmethod


class StorageError(Exception):
    """Falha de infraestrutura ao acessar o storage (rede, credencial, bucket)."""


class StorageObjectNotFound(StorageError):
    """A chave solicitada não existe no bucket."""


class StoragePort(ABC):
    """Contrato de armazenamento de objetos binários (artes JPG/PNG das provas)."""

    @abstractmethod
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Grava ``data`` sob ``key`` e retorna a key persistida.

        Idempotente: regravar a mesma key substitui o objeto (semântica S3 put).
        """

    @abstractmethod
    def download(self, key: str) -> bytes:
        """Lê o conteúdo de ``key``. Levanta ``StorageObjectNotFound`` se ausente."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove ``key``. Não falha se o objeto já não existe (idempotente)."""

    @abstractmethod
    def health(self) -> bool:
        """``True`` se o storage está acessível (usado pelo readiness check)."""
