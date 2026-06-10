"""Health checks observáveis (RNF-024).

- ``GET /health``        liveness: responde 200 imediato, sem tocar dependência
  alguma — usada por orquestradores para saber se o PROCESSO está vivo.
- ``GET /health/ready``  readiness: verifica banco (``SELECT 1``) e storage
  (``StoragePort.health()``), reportando cada dependência como ``ok``/``down``.
  200 quando tudo ok; 503 quando qualquer essencial está down — degradação
  clara, sem derrubar o processo (prompt W0-C01 §3.6).

As dependências chegam via ``app.state`` (injetadas pelo composition root),
o que permite aos testes substituí-las por fakes sem tocar em rede.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from src.application.ports.storage import StoragePort
from src.infrastructure.config import APP_VERSION, Settings

router = APIRouter(tags=["health"])

# Orçamento máximo de cada verificação: um readiness lento é tratado como down
# (load balancers têm timeout próprio; melhor responder 503 rápido que pendurar).
_CHECK_TIMEOUT_SECONDS = 5.0

CheckResult = Literal["ok", "down"]
DbPing = Callable[[], Awaitable[bool]]


async def _check_database(ping: DbPing) -> CheckResult:
    try:
        ok = await asyncio.wait_for(ping(), timeout=_CHECK_TIMEOUT_SECONDS)
    except Exception:
        return "down"
    return "ok" if ok else "down"


async def _check_storage(storage: StoragePort) -> CheckResult:
    try:
        # StoragePort é síncrona (boto3) — threadpool mantém o event loop livre
        ok = await asyncio.wait_for(
            run_in_threadpool(storage.health), timeout=_CHECK_TIMEOUT_SECONDS
        )
    except Exception:
        return "down"
    return "ok" if ok else "down"


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    """Liveness — nunca toca banco/storage (não pode falhar por dependência)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Readiness — status individual de cada dependência essencial."""
    settings: Settings = request.app.state.settings
    storage: StoragePort = request.app.state.storage
    db_ping: DbPing = request.app.state.db_ping

    # Verificações em paralelo: o tempo total é o da mais lenta, não a soma
    database_result, storage_result = await asyncio.gather(
        _check_database(db_ping), _check_storage(storage)
    )

    all_ok = database_result == "ok" and storage_result == "ok"
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if all_ok else "degraded",
            "checks": {"database": database_result, "storage": storage_result},
            "version": APP_VERSION,
            "env": settings.app_env,
        },
    )
