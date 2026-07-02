"""Composition root — o ÚNICO lugar onde concreto encontra abstrato (CLAUDE.md §5.2).

Aqui, e somente aqui:
- o ambiente é lido e validado (``Settings`` — falha rápido se mal configurado);
- adapters concretos são instanciados (R2Storage/UnconfiguredStorage, engine);
- as dependências são injetadas na app factory.

Execução: ``uv run uvicorn src.main:app --reload``
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from functools import partial

from fastapi import FastAPI

from src.adapters.inbound.http.app import create_app
from src.adapters.inbound.http.auth import build_jwt_verifier
from src.adapters.outbound.auth.argon2_hasher import Argon2PasswordHasher
from src.adapters.outbound.auth.es256_issuer import Es256TokenIssuer
from src.adapters.outbound.auth.keys import carregar_chave_privada_ec
from src.adapters.outbound.etiqueta.fpdf_etiqueta import FpdfEtiquetaGenerator
from src.adapters.outbound.storage.r2_storage import R2Storage
from src.adapters.outbound.storage.unconfigured import UnconfiguredStorage
from src.application.ports.storage import StoragePort
from src.application.ports.tokens import TokenIssuerPort
from src.infrastructure import database
from src.infrastructure.config import Settings, get_settings
from src.infrastructure.logging import configure_logging
from src.infrastructure.realtime import EventoHub, PgEventListener

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


def _build_token_issuer(settings: Settings) -> TokenIssuerPort | None:
    """Emissor ES256 quando o par de chaves está configurado; ``None`` caso
    contrário (o endpoint de login responde 503 — mesma filosofia do R2)."""
    if settings.auth_jwt_private_key is None:
        return None
    private_key = carregar_chave_privada_ec(settings.auth_jwt_private_key.get_secret_value())
    return Es256TokenIssuer(
        private_key=private_key,
        issuer=settings.auth_issuer,
        access_ttl_seconds=settings.auth_access_ttl_seconds,
    )


def _exigir_auth_configurada(settings: Settings) -> None:
    """Fail-fast: fora de dev/test, RECUSA subir sem o par de chaves ES256 — senão
    a app subiria sem emitir/verificar token e NINGUÉM logaria (degradação
    silenciosa é pior que falhar cedo)."""
    if settings.app_env in ("staging", "production") and not settings.auth_configured:
        raise RuntimeError(
            "AUTH_JWT_PRIVATE_KEY/AUTH_JWT_PUBLIC_KEY ausentes em "
            f"'{settings.app_env}': a autenticação não funcionaria. Configure o par de "
            "chaves ES256 (base64 do PEM)."
        )


def build_app() -> FastAPI:
    """Monta a aplicação completa a partir do ambiente."""
    settings = get_settings()
    configure_logging(settings.log_level)
    _exigir_auth_configurada(settings)

    engine = database.create_runtime_engine(settings)
    # Fábrica de sessões de REQUEST: fail-closed na RLS (W1-A-001) — recusa
    # transação sem claims propagados, em vez de cair no role owner (BYPASSRLS).
    session_factory = database.create_request_session_factory(engine)
    # Sessão de SISTEMA (sem claims, não fail-closed) para o caminho PRÉ-AUTH
    # (login/refresh/logout), que roda antes de existir qualquer claim.
    system_session_factory = database.create_session_factory(engine)
    storage = _build_storage(settings)
    jwt_verifier = build_jwt_verifier(settings)
    password_hasher = Argon2PasswordHasher()
    token_issuer = _build_token_issuer(settings)
    # Etapa 3 (realtime): hub in-process de fan-out para os streams SSE do dashboard
    # + o listener LISTEN/NOTIFY que o alimenta (uma conexão asyncpg dedicada de
    # sessão, derivada de MIGRATIONS_DATABASE_URL). O hub vai ao ``create_app``; o
    # listener sobe/encerra com o processo (lifespan).
    dashboard_hub = EventoHub()
    dashboard_listener = PgEventListener(settings, dashboard_hub)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Endurecimento operacional (M-01): em staging/produção, recusa subir se o
        # role de conexão ignora a RLS (superuser/BYPASSRLS). No-op em dev/test.
        await database.verificar_role_runtime_nao_privilegiado(engine, settings.app_env)
        # Etapa 3 (realtime): sobe o listener de LISTEN/NOTIFY (resiliente — reconecta
        # sozinho). Uma tarefa por processo; o fan-out entre processos é do Postgres.
        listener_task = asyncio.create_task(dashboard_listener.run())
        logger.info(
            "api iniciada",
            extra={"env": settings.app_env, "r2_configured": settings.r2_configured},
        )
        try:
            yield
        finally:
            # Backend stateless: nada a persistir — só devolve recursos. Cancela o
            # listener e fecha a conexão dedicada antes de dispor o engine.
            listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await listener_task
            await engine.dispose()
            logger.info("api encerrada")

    return create_app(
        settings=settings,
        storage=storage,
        db_ping=partial(database.ping, engine),
        jwt_verifier=jwt_verifier,
        session_factory=session_factory,
        # Template padrão da etiqueta (RN-011); o C09 trará a configuração.
        etiqueta_generator=FpdfEtiquetaGenerator(),
        password_hasher=password_hasher,
        token_issuer=token_issuer,
        system_session_factory=system_session_factory,
        dashboard_hub=dashboard_hub,
        lifespan=lifespan,
    )


app = build_app()
