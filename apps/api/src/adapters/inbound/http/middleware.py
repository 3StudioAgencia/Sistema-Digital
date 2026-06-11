"""Middlewares HTTP — correlação por ``request_id`` (RNF-024) e catch-all de erros.

Dois middlewares com papéis distintos, em camadas diferentes (ver ``app.py``):

- ``RequestIdMiddleware`` (o MAIS EXTERNO): reusa o ``X-Request-ID`` recebido
  ou gera um UUID4, publica no ``ContextVar`` (todos os logs da requisição o
  levam), devolve o header na resposta e emite UM access log estruturado por
  requisição (o access log nativo do uvicorn é desligado em ``logging.py``).
- ``ErrorHandlingMiddleware`` (INTERNO ao CORS): captura exceções não tratadas
  e devolve o envelope 500 padronizado. Fica por dentro do ``CORSMiddleware``
  de propósito: assim o 500 sai COM os headers CORS — sem eles, um frontend
  cross-origin veria apenas um erro de rede opaco e não conseguiria ler o
  ``request_id`` para reportar (ADR-013). A correlação é preservada porque o
  ``RequestIdMiddleware`` externo já populou o ``ContextVar``.
"""

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.adapters.inbound.http.errors import log_and_build_internal_error_response
from src.infrastructure.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
# Whitelist de formato para o id recebido: charset seguro + limite de 128
# (ids longos/arbitrários viram vetor de flooding e de poluição de log). Fora do
# padrão → gera um uuid4 próprio (W0-A-023).
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

logger = logging.getLogger("rastreio.http")


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catch-all de exceções não tratadas → envelope 500 sem stack trace."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            # Dentro do escopo do ContextVar (setado pelo RequestIdMiddleware
            # externo): o log CRITICAL sai correlacionado.
            return log_and_build_internal_error_response(request, exc)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Gera/propaga o request_id e emite o access log estruturado."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = inbound if _REQUEST_ID_PATTERN.match(inbound) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # Rede de segurança: só dispara se uma camada ENTRE este
                # middleware e o ErrorHandlingMiddleware falhar (ex.: CORS).
                # O caminho normal de erro é o ErrorHandlingMiddleware interno.
                response = log_and_build_internal_error_response(request, exc)
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        # Hardening mínimo de toda resposta (W0-A-016): sem MIME sniffing e sem
        # cache (relevante a partir da Wave 1, com endpoints autenticados). HSTS
        # pertence ao edge/TLS, não à app. `setdefault` deixa um handler futuro
        # sobrescrever o cache quando precisar (ex.: assets imutáveis).
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers.setdefault("Cache-Control", "no-store")
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
