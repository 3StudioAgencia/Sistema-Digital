"""Middleware de correlação por ``request_id`` (RNF-024).

Comportamento:
- Reusa o ``X-Request-ID`` recebido (propagação entre serviços/proxy) ou gera
  um novo UUID4 — assim o front pode correlacionar um erro de tela com a linha
  de log exata do backend.
- Publica o id no ``ContextVar`` para que TODOS os logs da requisição o levem.
- Devolve o id no header ``X-Request-ID`` da resposta.
- Emite um access log estruturado por requisição (método, caminho, status,
  duração) — uma única linha JSON, sem duplicar o access log do uvicorn.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.adapters.inbound.http.errors import log_and_build_internal_error_response
from src.infrastructure.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_INBOUND_ID_LENGTH = 128  # ids arbitrariamente longos viram vetor de log flooding

logger = logging.getLogger("rastreio.http")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Gera/propaga o request_id e emite o access log estruturado."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = inbound[:_MAX_INBOUND_ID_LENGTH] if inbound else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                # Catch-all DENTRO do escopo do ContextVar: o log CRITICAL sai
                # correlacionado e o cliente recebe o envelope 500 sem stack trace.
                response = log_and_build_internal_error_response(request, exc)
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
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
