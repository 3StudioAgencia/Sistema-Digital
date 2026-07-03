"""Adapter de ``StoragePort`` sobre o sistema de arquivos local (deploy on-prem).

Substitui o Cloudflare R2 (migração para servidor local): as artes das provas são
copiadas (snapshot) para um diretório do servidor. A chave S3-like
(``provas/<id>/arte.<ext>``) mapeia para um caminho relativo à base; a semântica é
a mesma que a porta promete (upload idempotente, download 404, delete idempotente).

Síncrono (IO de disco bloqueante) — os handlers async o chamam via threadpool, como
antes com o boto3. A escrita é atômica (arquivo temporário + ``os.replace``): um
crash no meio do upload não deixa arte meio-gravada no lugar da definitiva.
"""

import logging
import os
from contextlib import suppress
from pathlib import Path

from src.application.ports.storage import StorageError, StorageObjectNotFound, StoragePort

logger = logging.getLogger("rastreio.storage.fs")


class FilesystemStorage(StoragePort):
    """Implementação de ``StoragePort`` sobre um diretório do sistema de arquivos."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)
        # Cria a base no boot (idempotente): o storage nasce utilizável em dev/prod.
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolver(self, key: str) -> Path:
        """Mapeia a key para um caminho DENTRO da base — impede path traversal.

        A key é gerada pela app (``provas/<uuid>/arte.<ext>``); ainda assim, resolver
        e conferir a base é defesa em profundidade (uma key com ``..`` nunca escapa)."""
        base = self._base.resolve()
        alvo = (base / key).resolve()
        if alvo != base and base not in alvo.parents:
            raise StorageError(f"Chave de storage inválida (fora da base): {key!r}")
        return alvo

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        alvo = self._resolver(key)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        # Escrita atômica: grava num temporário no MESMO diretório e renomeia
        # (``os.replace`` é atômico dentro do mesmo filesystem). O content_type não
        # é persistido aqui — a prova guarda ``arte_content_type`` no Postgres.
        temp = alvo.parent / f".{alvo.name}.{os.getpid()}.tmp"
        try:
            temp.write_bytes(data)
            os.replace(temp, alvo)
        except OSError as exc:
            with suppress(OSError):
                temp.unlink(missing_ok=True)
            raise StorageError(f"Falha ao gravar objeto no storage (key={key!r})") from exc
        return key

    def download(self, key: str) -> bytes:
        alvo = self._resolver(key)
        try:
            return alvo.read_bytes()
        except FileNotFoundError as exc:
            raise StorageObjectNotFound(
                f"Objeto não encontrado no storage (key={key!r})"
            ) from exc
        except OSError as exc:
            raise StorageError(f"Falha ao ler objeto do storage (key={key!r})") from exc

    def delete(self, key: str) -> None:
        alvo = self._resolver(key)
        try:
            alvo.unlink(missing_ok=True)  # idempotente: remover inexistente não falha
        except OSError as exc:
            raise StorageError(f"Falha ao remover objeto do storage (key={key!r})") from exc

    def health(self) -> bool:
        if self._base.is_dir() and os.access(self._base, os.W_OK):
            return True
        logger.warning(
            "health check do storage (filesystem) falhou",
            extra={"event": "storage_health_failed", "base": str(self._base)},
        )
        return False


__all__ = ["FilesystemStorage"]
