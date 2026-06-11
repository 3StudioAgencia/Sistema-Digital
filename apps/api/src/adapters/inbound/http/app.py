"""App factory — monta a instância FastAPI a partir de dependências já resolvidas.

A factory NÃO constrói adapters concretos nem lê ambiente: recebe tudo pronto
do composition root (``src/main.py``) ou dos testes (fakes). É o que mantém a
camada HTTP testável offline e o wiring num único lugar (CLAUDE.md §5.2).
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.inbound.http.auth import router as auth_router
from src.adapters.inbound.http.errors import install_error_handlers
from src.adapters.inbound.http.health import DbPing
from src.adapters.inbound.http.health import router as health_router
from src.adapters.inbound.http.middleware import ErrorHandlingMiddleware, RequestIdMiddleware
from src.application.ports.storage import StoragePort
from src.infrastructure.config import APP_NAME, APP_VERSION, Settings

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]] | None


def create_app(
    settings: Settings,
    storage: StoragePort,
    db_ping: DbPing,
    jwt_verifier: JwtVerifier | None = None,
    lifespan: Lifespan = None,
) -> FastAPI:
    """Cria a aplicação FastAPI com middlewares, handlers de erro e routers.

    ``jwt_verifier`` é injetado pelo composition root (``main.py``). O default
    é um verifier *deny-all* (sem JWKS nem segredo): mantém testes que não
    exercitam auth funcionando sem precisar montá-lo.
    """
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        # OpenAPI exposto em /docs (critério §5.7). Em produção pode ser
        # restringido via RBAC na Wave 1 — decisão registrada, não um TODO órfão.
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # Dependências consumidas pelos routers (substituíveis nos testes)
    app.state.settings = settings
    app.state.storage = storage
    app.state.db_ping = db_ping
    app.state.jwt_verifier = jwt_verifier or JwtVerifier()

    # Ordem dos middlewares: o último adicionado é o mais EXTERNO. De dentro
    # para fora: ErrorHandling → CORS → RequestId.
    # - ErrorHandling interno ao CORS: o envelope 500 sai com headers CORS
    #   (sem eles o frontend cross-origin não lê o request_id — ADR-013);
    # - RequestId por fora de tudo: TODA resposta (inclusive preflights e
    #   erros) sai com X-Request-ID e access log correlacionado.
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
    return app


__all__ = ["Lifespan", "create_app"]
