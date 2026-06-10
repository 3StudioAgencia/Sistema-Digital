"""Composition root — o ÚNICO lugar onde concreto encontra abstrato (CLAUDE.md §5.2).

Aqui, e somente aqui:
- o ambiente é lido e validado (``Settings`` — falha rápido se mal configurado);
- adapters concretos são instanciados (R2Storage/UnconfiguredStorage, engine);
- as dependências são injetadas na app factory.

Execução: ``uv run uvicorn src.main:app --reload``
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from src.adapters.inbound.http.app import create_app
from src.adapters.outbound.storage.r2_storage import R2Storage
from src.adapters.outbound.storage.unconfigured import UnconfiguredStorage
from src.application.ports.storage import StoragePort
from src.infrastructure import database
from src.infrastructure.config import Settings, get_settings
from src.infrastructure.logging import configure_logging

logger = logging.getLogger("rastreio.main")


def _build_storage(settings: Settings) -> StoragePort:
    """R2 real quando configurado; caso contrário, stand-in explícito.

    A app SOBE sem credenciais (dev/CI sem R2) e o readiness reporta storage
    "down" — degradação clara em vez de crash no boot (prompt W0-C01 §3.6).
    """
    if settings.r2_configured:
        return R2Storage.from_settings(settings)
    logger.warning("R2 não configurado — storage indisponível (readiness reportará 'down')")
    return UnconfiguredStorage()


def build_app() -> FastAPI:
    """Monta a aplicação completa a partir do ambiente."""
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = database.create_runtime_engine(settings)
    storage = _build_storage(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "api iniciada",
            extra={"env": settings.app_env, "r2_configured": settings.r2_configured},
        )
        yield
        # Backend stateless: nada a persistir no shutdown — apenas devolve recursos
        await engine.dispose()
        logger.info("api encerrada")

    return create_app(
        settings=settings,
        storage=storage,
        db_ping=partial(database.ping, engine),
        lifespan=lifespan,
    )


app = build_app()
