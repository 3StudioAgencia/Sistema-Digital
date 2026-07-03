"""Adapter nulo usado quando o storage de artes não está configurado no ambiente.

Permite que a aplicação SUBA sem storage (dev/CI/offline): o readiness reporta o
storage "down" com clareza, e qualquer tentativa de uso real falha com mensagem
acionável — em vez de um stack trace de IO.
"""

from src.application.ports.storage import StorageError, StoragePort

_MSG = (
    "Storage de artes não configurado: defina STORAGE_DIR no ambiente "
    "(ver docs/setup-infra.md)."
)


class UnconfiguredStorage(StoragePort):

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        raise StorageError(_MSG)

    def download(self, key: str) -> bytes:
        raise StorageError(_MSG)

    def delete(self, key: str) -> None:
        raise StorageError(_MSG)

    def health(self) -> bool:
        return False
