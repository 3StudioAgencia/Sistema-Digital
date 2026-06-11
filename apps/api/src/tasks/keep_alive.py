"""Keep-alive do Postgres do Supabase (W0-C02).

O free tier do Supabase **pausa o projeto após 7 dias sem requisições** — o que
derrubaria o banco inteiro. Esta tarefa agendada faz uma requisição **read-only**
trivial ao banco, em cadência calibrada ao mínimo necessário, mantendo o projeto
ativo e "quente" no horário comercial (RNF-011), com **registro estruturado** de
cada execução (auditoria de disponibilidade) e **exit code** que sinaliza falha
ao scheduler (RNF-024).

Arquitetura (ADR-015): o gatilho é EXTERNO e independente do host da API
(``pg_cron`` pausaria junto com o projeto; um scheduler embutido na API
hibernaria junto com o host free tier). O scheduler primário é um workflow
agendado do GitHub Actions (``.github/workflows/keep-alive.yml``); esta rotina é
o alvo trocável que ele invoca.

Reuso (DRY, CLAUDE.md §3): a ida ao banco é a MESMA do readiness do C01 —
``fetch_db_time`` em ``src.infrastructure.database``, também usada por ``ping``.
A conexão é a DIRETA/sessão (5432, ``MIGRATIONS_DATABASE_URL``), ideal para um
``SELECT`` *one-shot* sem as peculiaridades do pooler de transação.

Execução: ``uv run python -m src.tasks.keep_alive`` (a partir de ``apps/api``).
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from src.infrastructure.config import Settings, get_settings
from src.infrastructure.database import create_direct_engine, fetch_db_time
from src.infrastructure.logging import configure_logging, request_id_var

_EVENT = "keep_alive"
logger = logging.getLogger("rastreio.keep_alive")


@dataclass(frozen=True)
class KeepAliveOutcome:
    """Resultado de um keep-alive bem-sucedido."""

    db_time: datetime  # valor de now() do servidor — prova de atividade
    latency_ms: float  # round-trip medido em torno do SELECT (inclui abrir a conexão)


async def run_keep_alive(settings: Settings) -> KeepAliveOutcome:
    """Abre uma conexão curta na DIRETA (5432), lê ``now()`` e mede a latência.

    **Levanta** em falha de conexão — o orquestrador (:func:`run`) a converte em
    log ``status="error"`` + exit code ≠ 0. Sem efeitos colaterais além do
    ``SELECT`` read-only (nada é escrito no banco).
    """
    engine = create_direct_engine(settings)
    try:
        start = time.perf_counter()
        db_time = await fetch_db_time(engine)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
    finally:
        # Processo efêmero: devolve a conexão/engine sempre, inclusive em falha.
        await engine.dispose()
    return KeepAliveOutcome(db_time=db_time, latency_ms=latency_ms)


def _ok_fields(outcome: KeepAliveOutcome, correlation_id: str, env: str) -> dict[str, object]:
    return {
        "event": _EVENT,
        "status": "ok",
        "latency_ms": outcome.latency_ms,
        "db_time": outcome.db_time.isoformat(),
        "correlation_id": correlation_id,
        "env": env,
    }


def _error_fields(exc: BaseException, correlation_id: str, env: str) -> dict[str, object]:
    # Apenas o TIPO da exceção — NUNCA str(exc): a mensagem de erro do driver
    # pode conter a connection string. Não vazar credenciais (prompt §4.1.5).
    return {
        "event": _EVENT,
        "status": "error",
        "correlation_id": correlation_id,
        "env": env,
        "error_type": type(exc).__name__,
    }


def run(settings: Settings) -> int:
    """Executa um keep-alive: emite UM log estruturado e devolve o exit code.

    Retorna ``0`` em sucesso e ``1`` em falha — o scheduler usa o código para
    marcar o run e disparar o alerta (RNF-024).
    """
    configure_logging(settings.log_level)
    correlation_id = uuid.uuid4().hex
    # request_id é o campo de correlação automático do logging do C01; apontamos
    # para o mesmo id para que TODA linha desta execução seja correlacionável.
    # correlation_id permanece como campo explícito exigido pelo contrato (§4.1.3).
    token = request_id_var.set(correlation_id)
    try:
        try:
            outcome = asyncio.run(run_keep_alive(settings))
        except Exception as exc:  # falha de conexão/consulta → status=error, exit 1
            logger.error(
                "keep-alive falhou",
                extra=_error_fields(exc, correlation_id, settings.app_env),
            )
            return 1
        logger.info(
            "keep-alive ok",
            extra=_ok_fields(outcome, correlation_id, settings.app_env),
        )
        return 0
    finally:
        request_id_var.reset(token)


def main() -> int:
    """Entry point CLI: lê e valida o ambiente (falha rápido) e executa a rotina.

    ``get_settings()`` roda FORA do contrato de erro de :func:`run` — uma
    ``ValidationError`` do ``Settings`` (ex.: ``KEEPALIVE_DATABASE_URL``
    malformado mas com credencial) imprimiria um traceback cru. Envolvemos a
    carga no MESMO contrato: log só com ``error_type`` e exit 1, nunca o valor
    (W0-A-005). ``hide_input_in_errors`` no ``Settings`` é a segunda camada.
    """
    try:
        settings = get_settings()
    except Exception as exc:
        configure_logging("INFO")
        logger.error(
            "keep-alive falhou ao carregar configuração",
            extra=_error_fields(exc, uuid.uuid4().hex, "unknown"),
        )
        return 1
    return run(settings)


if __name__ == "__main__":
    sys.exit(main())
