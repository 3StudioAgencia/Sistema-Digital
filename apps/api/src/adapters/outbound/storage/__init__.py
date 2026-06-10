"""Adapters de storage de objetos (porta: ``StoragePort``)."""

from src.adapters.outbound.storage.r2_storage import R2Storage
from src.adapters.outbound.storage.unconfigured import UnconfiguredStorage

__all__ = ["R2Storage", "UnconfiguredStorage"]
