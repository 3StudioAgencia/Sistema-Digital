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

from src.application.ports.identity_provider import (
    IdentityProviderError,
    IdentityProviderNaoConfigurado,
)
from src.application.ports.storage import StorageError
from src.application.usuarios import EmailJaCadastradoError, UsuarioNaoEncontradoError
from src.domain.movimentacoes import TransicaoIdempotenciaConflitoError
from src.domain.provas import (
    CriacaoDivergenteError,
    LimiteDeTentativasError,
    ProvaNaoEncontradaError,
)
from src.domain.state_machine.machine import TransicaoNaoAutorizadaError
from src.domain.usuarios import ErroDeDominio
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


def _status_de_dominio(exc: ErroDeDominio) -> int:
    """Violações de regra de negócio → HTTP (W1-C04). 422 é o default; os dois
    casos com semântica própria têm status dedicado."""
    if isinstance(exc, UsuarioNaoEncontradoError | ProvaNaoEncontradaError):
        return status.HTTP_404_NOT_FOUND
    # W3-C11: perfil não autorizado para a transição (rota+estado válidos) → 403,
    # mensagem genérica que não revela qual setor poderia (RN-014/Backlog C11).
    if isinstance(exc, TransicaoNaoAutorizadaError):
        return status.HTTP_403_FORBIDDEN
    if isinstance(
        exc, EmailJaCadastradoError | CriacaoDivergenteError | TransicaoIdempotenciaConflitoError
    ):
        return status.HTTP_409_CONFLICT
    if isinstance(exc, LimiteDeTentativasError):
        return status.HTTP_429_TOO_MANY_REQUESTS
    return status.HTTP_422_UNPROCESSABLE_CONTENT


async def _dominio_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    erro = cast(ErroDeDominio, exc)
    return JSONResponse(
        status_code=_status_de_dominio(erro),
        content=error_envelope(erro.codigo, str(erro), request_id_var.get()),
    )


async def _identity_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Falha no provedor de identidade: o adapter já logou os detalhes; ao
    cliente vai um envelope genérico SEM ecoar a causa (a mensagem interna
    poderia carregar status/códigos do provedor)."""
    if isinstance(exc, IdentityProviderNaoConfigurado):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_envelope(
                "identidade_nao_configurada",
                "Gestão de usuários indisponível: provedor de identidade não configurado.",
                request_id_var.get(),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=error_envelope(
            "provedor_identidade",
            "Falha ao comunicar com o provedor de identidade. Tente novamente.",
            request_id_var.get(),
        ),
    )


async def _storage_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Falha de infraestrutura no storage (R2): indisponibilidade clara (503),
    nunca 500 opaco — mesma filosofia do provedor de identidade. O detalhe fica
    no log estruturado (W2-C06)."""
    logger.warning(
        "storage indisponível durante a requisição",
        extra={"event": "storage_indisponivel", "error_type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_envelope(
            "storage_indisponivel",
            "Armazenamento de artes indisponível no momento. Tente novamente.",
            request_id_var.get(),
        ),
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(ErroDeDominio, _dominio_exception_handler)
    app.add_exception_handler(IdentityProviderError, _identity_exception_handler)
    app.add_exception_handler(StorageError, _storage_exception_handler)
    app.add_exception_handler(Exception, _last_resort_handler)
