"""Adapter de storage para Cloudflare R2 via boto3 (API S3-compatível).

O cliente boto3 é INJETADO no construtor (em vez de criado dentro dos métodos):
- testável com `moto` sem variáveis de ambiente nem monkeypatch;
- o composition root é o único lugar que conhece credenciais (CLAUDE.md §5.2).

boto3 é síncrono; quem chama a partir de código async usa threadpool — ver a
nota de desenho em ``src/application/ports/storage.py``.
"""

from typing import Any, cast

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from src.application.ports.storage import StorageError, StorageObjectNotFound, StoragePort
from src.infrastructure.config import Settings

# boto3 não publica stubs oficiais — o Any fica contido neste módulo (fronteira tipada)
S3Client = Any


class R2Storage(StoragePort):
    """Implementação de ``StoragePort`` sobre um bucket R2 (ou qualquer S3)."""

    def __init__(self, client: S3Client, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "R2Storage":
        """Constrói o cliente S3 apontando para o endpoint do R2 (config por env)."""
        # Checagem explícita campo a campo (equivale a r2_configured e narra o
        # tipo para o mypy). O validador tudo-ou-nada do Settings garante que
        # ou todos estão presentes, ou nenhum.
        if (
            settings.r2_endpoint_url is None
            or settings.r2_access_key_id is None
            or settings.r2_secret_access_key is None
            or settings.r2_bucket is None
        ):
            msg = "R2 não configurado — defina as variáveis R2_* no ambiente."
            raise StorageError(msg)
        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            # R2 usa region "auto" e exige SigV4
            region_name="auto",
            config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3}),
        )
        return cls(client=client, bucket=settings.r2_bucket)

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )
        except (ClientError, BotoCoreError) as exc:
            msg = f"Falha ao gravar objeto no storage (key={key!r})"
            raise StorageError(msg) from exc
        return key

    def download(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return cast(bytes, response["Body"].read())
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                msg = f"Objeto não encontrado no storage (key={key!r})"
                raise StorageObjectNotFound(msg) from exc
            msg = f"Falha ao ler objeto do storage (key={key!r})"
            raise StorageError(msg) from exc
        except BotoCoreError as exc:
            msg = f"Falha ao ler objeto do storage (key={key!r})"
            raise StorageError(msg) from exc

    def delete(self, key: str) -> None:
        try:
            # delete_object é idempotente na API S3: deletar key inexistente é 204
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            msg = f"Falha ao remover objeto do storage (key={key!r})"
            raise StorageError(msg) from exc

    def health(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except (ClientError, BotoCoreError):
            return False
        return True
