"""App factory — monta a instância FastAPI a partir de dependências já resolvidas.

A factory NÃO constrói adapters concretos nem lê ambiente: recebe tudo pronto
do composition root (``src/main.py``) ou dos testes (fakes). É o que mantém a
camada HTTP testável offline e o wiring num único lugar (CLAUDE.md §5.2).
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.inbound.http.auth import router as auth_router
from src.adapters.inbound.http.dashboard import router as dashboard_router
from src.adapters.inbound.http.errors import install_error_handlers
from src.adapters.inbound.http.health import DbPing
from src.adapters.inbound.http.health import router as health_router
from src.adapters.inbound.http.middleware import (
    BodyLimitMiddleware,
    ErrorHandlingMiddleware,
    RequestIdMiddleware,
)
from src.adapters.inbound.http.provas import router as provas_router
from src.adapters.inbound.http.settings import router as settings_router
from src.adapters.inbound.http.usuarios import router as usuarios_router
from src.adapters.outbound.etiqueta.fpdf_etiqueta import FpdfEtiquetaGenerator
from src.adapters.outbound.identity.supabase_admin import UnconfiguredIdentityProvider
from src.application.ports.etiqueta import EtiquetaPort
from src.application.ports.identity_provider import IdentityProviderPort
from src.application.ports.storage import StoragePort
from src.infrastructure.config import APP_NAME, APP_VERSION, Settings

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]] | None


def create_app(
    settings: Settings,
    storage: StoragePort,
    db_ping: DbPing,
    jwt_verifier: JwtVerifier | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    identity_provider: IdentityProviderPort | None = None,
    etiqueta_generator: EtiquetaPort | None = None,
    lifespan: Lifespan = None,
) -> FastAPI:
    """Cria a aplicação FastAPI com middlewares, handlers de erro e routers.

    ``jwt_verifier`` é injetado pelo composition root (``main.py``). O default
    é um verifier *deny-all* (sem JWKS nem segredo): mantém testes que não
    exercitam auth funcionando sem precisar montá-lo. ``session_factory`` e
    ``identity_provider`` (W1-C04) seguem o mesmo princípio: defaults seguros
    (503/erro claro) para testes que não exercitam usuários.
    """
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        # OpenAPI exposto em /docs fora de produção (critério §5.7 do W0). Em
        # produção fica DESLIGADO: a superfície da API de gestão de usuários
        # não é enumerável por anônimos (revisão W1-C04); o RBAC fino é C05.
        docs_url="/docs" if settings.app_env != "production" else None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Dependências consumidas pelos routers (substituíveis nos testes)
    app.state.settings = settings
    app.state.storage = storage
    app.state.db_ping = db_ping
    app.state.jwt_verifier = jwt_verifier or JwtVerifier()
    app.state.session_factory = session_factory
    app.state.identity_provider = identity_provider or UnconfiguredIdentityProvider()
    # Default concreto seguro (mesmo princípio do JwtVerifier deny-all): o
    # gerador é puro/sem segredos — o template padrão serve a app e os testes.
    app.state.etiqueta_generator = etiqueta_generator or FpdfEtiquetaGenerator()

    # Ordem dos middlewares: o último adicionado é o mais EXTERNO. De dentro
    # para fora: BodyLimit → ErrorHandling → CORS → RequestId.
    # - BodyLimit o mais interno: o 413 do contador sobe como HTTPException
    #   para o ExceptionMiddleware da app (envelope canônico), nunca vira 500;
    # - ErrorHandling interno ao CORS: o envelope 500 sai com headers CORS
    #   (sem eles o frontend cross-origin não lê o request_id — ADR-013);
    # - RequestId por fora de tudo: TODA resposta (inclusive preflights e
    #   erros) sai com X-Request-ID e access log correlacionado.
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)

    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(usuarios_router)
    app.include_router(provas_router)
    app.include_router(settings_router)
    app.include_router(dashboard_router)
    return app


__all__ = ["Lifespan", "create_app"]
