"""Keep-alive contra Postgres real (@db — skip sem banco local; FALHA no CI).

Valida o caminho de SUCESSO ponta a ponta (prompt §6, critério §5.4): conexão
direta one-shot, leitura do ``now()`` do servidor, exit 0 e log ``status="ok"``
com a latência medida. O caminho de falha/contrato roda offline em
``tests/unit/test_keep_alive.py``.
"""

import json
from datetime import datetime

import pytest
from src.infrastructure.config import Settings
from src.tasks.keep_alive import run, run_keep_alive

pytestmark = pytest.mark.db


def _settings(url: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=url,
        migrations_database_url=url,
    )


async def test_run_keep_alive_le_now_do_servidor_e_mede_latencia(database_url: str) -> None:
    outcome = await run_keep_alive(_settings(database_url))

    assert isinstance(outcome.db_time, datetime)
    assert outcome.latency_ms >= 0.0


def test_run_sucesso_retorna_exit_0_e_loga_status_ok(
    database_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(_settings(database_url))

    assert code == 0
    linhas = [ln for ln in capsys.readouterr().out.strip().splitlines() if ln.strip()]
    evento = json.loads(linhas[-1])
    assert evento["event"] == "keep_alive"
    assert evento["status"] == "ok"
    assert "latency_ms" in evento
    assert "db_time" in evento
    assert evento["correlation_id"]
    assert evento["env"] == "test"
