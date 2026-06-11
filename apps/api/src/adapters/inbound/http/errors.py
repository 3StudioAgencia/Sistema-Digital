"""Tratamento de erros HTTP — resposta padronizada, sem vazar stack trace (RNF-024).

Envelope canônico de erro (todas as respostas de erro da API)::

    { "error": { "code": "<slug>", "message": "<texto seguro>", "request_id": "<id>" } }

Decisões (ADR-013, com a emenda da revisão adversarial):
- Stack traces NUNCA chegam ao cliente; ficam no log estruturado (nível CRITICAL
  para erros não tratados), correlacionados pelo request_id.
- O catch-all de exceções roda no ``ErrorHandlingMiddleware`` (INTERNO ao
  ``CORSMiddleware``), para que o envelope 500 saia COM os headers CORS — sem
  eles um frontend cross-origin veria um erro de rede opaco e perderia o
  request_id. O ``RequestIdMiddleware`` (mais externo) e o handler genérico do
  Starlette permanecem como redes de segurança de última instância (ambos
  delegam à mesma função). Ver ``app.py`` para a ordem dos middlewares.
"""

import logging
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.infrastructure.logging import request_id_var

logger = logging.getLogger("rastreio.http.errors")

_INTERNAL_ERROR_MESSAGE = (
    "Erro interno inesperado. Tente novamente; se persistir, informe o request_id ao suporte."
)


def error_envelope(code: str, message: str, request_id: str | None) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def log_and_build_internal_error_response(request: Request, exc: Exception) -> JSONResponse:
    """Loga a exceção não tratada em CRITICAL e devolve o envelope 500 genérico.

    Chamado pelo ``ErrorHandlingMiddleware`` (caminho principal, interno ao CORS)
    e pelas redes de segurança (``RequestIdMiddleware`` e o handler genérico).
    """
    request_id = request_id_var.get()
    logger.critical(
        "unhandled exception",
        exc_info=exc,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_envelope("internal_error", _INTERNAL_ERROR_MESSAGE, request_id),
    )


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Registrado para StarletteHTTPException — o cast só narra o tipo ao mypy
    http_exc = cast(StarletteHTTPException, exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=error_envelope("http_error", str(http_exc.detail), request_id_var.get()),
        headers=http_exc.headers,
    )


async def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    validation_exc = cast(RequestValidationError, exc)
    body = error_envelope(
        "validation_error", "Payload inválido para esta operação.", request_id_var.get()
    )
    # loc/msg/type do Pydantic são seguros para o cliente e necessários para depurar o form
    body["details"] = [
        {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")}
        for e in validation_exc.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body)


async def _last_resort_handler(request: Request, exc: Exception) -> JSONResponse:
    return log_and_build_internal_error_response(request, exc)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _last_resort_handler)
