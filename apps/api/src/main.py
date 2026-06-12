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
from src.adapters.inbound.http.auth import build_jwt_verifier
from src.adapters.outbound.etiqueta.fpdf_etiqueta import FpdfEtiquetaGenerator
from src.adapters.outbound.identity.supabase_admin import (
    SupabaseAdminIdentityProvider,
    UnconfiguredIdentityProvider,
)
from src.adapters.outbound.storage.r2_storage import R2Storage
from src.adapters.outbound.storage.unconfigured import UnconfiguredStorage
from src.application.ports.identity_provider import IdentityProviderPort
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


def _build_identity_provider(settings: Settings) -> IdentityProviderPort:
    """Admin API real quando a chave secreta está configurada; stand-in claro
    caso contrário (gestão de usuários responde 503 — mesma filosofia do R2)."""
    if settings.supabase_url is not None and settings.supabase_secret_key is not None:
        return SupabaseAdminIdentityProvider(
            supabase_url=settings.supabase_url,
            secret_key=settings.supabase_secret_key.get_secret_value(),
        )
    logger.warning("SUPABASE_SECRET_KEY não configurada — gestão de usuários indisponível (503)")
    return UnconfiguredIdentityProvider()


def build_app() -> FastAPI:
    """Monta a aplicação completa a partir do ambiente."""
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = database.create_runtime_engine(settings)
    # Fábrica de sessões de REQUEST: fail-closed na RLS (W1-A-001) — recusa
    # transação sem claims propagados, em vez de cair no role owner (BYPASSRLS).
    session_factory = database.create_request_session_factory(engine)
    storage = _build_storage(settings)
    jwt_verifier = build_jwt_verifier(settings)
    identity_provider = _build_identity_provider(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "api iniciada",
            extra={"env": settings.app_env, "r2_configured": settings.r2_configured},
        )
        yield
        # Backend stateless: nada a persistir no shutdown — apenas devolve recursos
        if isinstance(identity_provider, SupabaseAdminIdentityProvider):
            await identity_provider.aclose()
        await engine.dispose()
        logger.info("api encerrada")

    return create_app(
        settings=settings,
        storage=storage,
        db_ping=partial(database.ping, engine),
        jwt_verifier=jwt_verifier,
        session_factory=session_factory,
        identity_provider=identity_provider,
        # Template padrão da etiqueta (RN-011); o C09 trará a configuração.
        etiqueta_generator=FpdfEtiquetaGenerator(),
        lifespan=lifespan,
    )


app = build_app()
