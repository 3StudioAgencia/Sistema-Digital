"""Middlewares HTTP — correlação por ``request_id`` (RNF-024), catch-all de
erros e teto do corpo da requisição.

Três middlewares com papéis distintos, em camadas diferentes (ver ``app.py``):

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
- ``BodyLimitMiddleware`` (o MAIS INTERNO): rejeita corpos acima do teto com
  413 — inclusive ANTES da autenticação, pois o FastAPI parseia o multipart
  antes de resolver as dependências (revisão adversarial W2-C06: sem o teto,
  um cliente anônimo faria o servidor receber GBs para disco temporário antes
  do 401/403).
"""

import logging
import re
import time
import uuid

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.adapters.inbound.http.errors import (
    error_envelope,
    log_and_build_internal_error_response,
)
from src.domain.provas import ARTE_TAMANHO_MAXIMO
from src.infrastructure.logging import client_ip_var, request_id_var, user_agent_var

REQUEST_ID_HEADER = "X-Request-ID"
# Whitelist de formato para o id recebido: charset seguro + limite de 128
# (ids longos/arbitrários viram vetor de flooding e de poluição de log). Fora do
# padrão → gera um uuid4 próprio (W0-A-023).
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

logger = logging.getLogger("rastreio.http")


# Teto do CORPO da requisição: a maior carga legítima é a arte (10 MB) + os
# campos e o overhead do multipart — 12 MB dá folga sem abrir espaço a abuso.
LIMITE_CORPO_BYTES = ARTE_TAMANHO_MAXIMO + 2 * 1024 * 1024
_MENSAGEM_413 = "Corpo da requisição excede o limite de 12 MB."


class BodyLimitMiddleware:
    """ASGI puro: corta corpos acima do teto o mais cedo possível (413).

    Duas defesas complementares:
    1. ``Content-Length`` declarado acima do teto → 413 imediato, sem ler nada;
    2. corpo em streaming/chunked (ou Content-Length mentiroso) → o ``receive``
       é envelopado num contador e a leitura ABORTA no byte que cruza o teto
       (``HTTPException(413)`` — tratada pelo handler canônico, que devolve o
       envelope de erro com os headers CORS/Request-ID das camadas externas).

    Mais interno que o ``ErrorHandlingMiddleware``: a ``HTTPException`` sobe
    para o ``ExceptionMiddleware`` do Starlette (dentro da app), nunca vira 500.
    """

    def __init__(self, app: ASGIApp, max_body: int = LIMITE_CORPO_BYTES) -> None:
        self.app = app
        self.max_body = max_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declarado = self._content_length(scope)
        if declarado is not None and declarado > self.max_body:
            response = JSONResponse(
                status_code=413,
                content=error_envelope("payload_too_large", _MENSAGEM_413, request_id_var.get()),
            )
            await response(scope, receive, send)
            return

        total = 0

        async def receber_limitado() -> Message:
            nonlocal total
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                total += len(mensagem.get("body", b""))
                if total > self.max_body:
                    raise StarletteHTTPException(status_code=413, detail=_MENSAGEM_413)
            return mensagem

        await self.app(scope, receber_limitado, send)

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for nome, valor in scope.get("headers") or []:
            if nome == b"content-length":
                try:
                    return int(valor)
                except ValueError:
                    return None
        return None


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


def _client_ip(request: Request) -> str | None:
    """IP do cliente, best-effort (W6-C20). Atrás de Cloudflare/proxy o IP real vem
    em ``CF-Connecting-IP`` ou no 1º salto de ``X-Forwarded-For``; sem proxy, o peer
    direto (``request.client``). É METADADO de auditoria (não decisão de auth), então
    é tolerante e NÃO confiável a ponto de gatear acesso — apenas registra a origem
    provável (a confiança real depende do edge estar configurado para sobrescrever
    esses headers)."""
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()[:64]
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Gera/propaga o request_id (+ IP/User-Agent — W6-C20) e emite o access log."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = inbound if _REQUEST_ID_PATTERN.match(inbound) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        # Contexto de origem para a auditoria (C20): lido pelo adapter ao gravar um
        # evento. Capturado aqui (middleware mais externo), nunca confiando num header
        # forjável como decisão de acesso — só como metadado de origem.
        ip_token = client_ip_var.set(_client_ip(request))
        ua_token = user_agent_var.set(request.headers.get("user-agent") or None)
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
            client_ip_var.reset(ip_token)
            user_agent_var.reset(ua_token)

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
