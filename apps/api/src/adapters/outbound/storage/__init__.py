"""Adapters de storage de objetos (porta: ``StoragePort``)."""

from src.adapters.outbound.storage.filesystem_storage import FilesystemStorage
from src.adapters.outbound.storage.unconfigured import UnconfiguredStorage

__all__ = ["FilesystemStorage", "UnconfiguredStorage"]
