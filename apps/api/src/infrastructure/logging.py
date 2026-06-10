"""Logging estruturado em JSON com correlação por ``request_id`` (RNF-024).

Desenho:
- Um ``ContextVar`` carrega o request_id da requisição corrente; o middleware
  HTTP o define no início e o limpa no fim (seguro sob concorrência asyncio —
  cada task enxerga seu próprio valor).
- Um ``logging.Filter`` injeta o request_id em TODO registro emitido durante a
  requisição, de qualquer logger da aplicação — sem precisar passar o id
  manualmente em cada chamada.
- Saída: uma linha JSON por evento em stdout (12-factor; o coletor do host
  agrega — nada de arquivos locais, que quebrariam a escala horizontal).
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger.json import JsonFormatter

# Token de correlação da requisição corrente (None fora de um request).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Anexa o request_id corrente a todo LogRecord (correlação transversal)."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Não sobrescreve se o emissor já passou um request_id explícito via extra=
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class _AppJsonFormatter(JsonFormatter):
    """Formato canônico: timestamp, level, logger, message, request_id, extras."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        # Atribuição explícita (não setdefault): o formatter pré-popula os
        # campos do format string com None quando o atributo não existe
        log_record["logger"] = record.name
        log_record["level"] = record.levelname


def configure_logging(level: str = "INFO") -> None:
    """Configura o logging raiz para JSON estruturado. Idempotente.

    Também alinha os loggers do uvicorn ao mesmo handler, para que access logs
    e logs de erro do servidor saiam no formato canônico (com request_id).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _AppJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s",
            timestamp=True,
        )
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]  # substitui (idempotente), não acumula
    root.setLevel(level.upper())

    # uvicorn instala handlers próprios em texto plano; redireciona ao root JSON.
    for name in ("uvicorn", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True

    # O access log NATIVO do uvicorn é desligado: ele emitiria depois do reset
    # do ContextVar (request_id nulo) e duplicaria o access log estruturado do
    # RequestIdMiddleware — fica UMA linha correlacionada por requisição.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False
