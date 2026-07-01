"""Adapter nulo usado quando o R2 não está configurado no ambiente.

Permite que a aplicação SUBA sem credenciais reais (prompt W0-C01 §3.6):
o readiness check reporta storage "down" com clareza, e qualquer tentativa de
uso real falha com mensagem acionável — em vez de um stack trace do boto3.
"""

from src.application.ports.storage import StorageError, StoragePort

_MSG = (
    "Storage não configurado: defina R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, "
    "R2_SECRET_ACCESS_KEY e R2_BUCKET no ambiente (ver docs/setup-infra.md)."
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
