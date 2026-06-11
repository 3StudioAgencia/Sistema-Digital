"""Keep-alive (W0-C02) — exit codes, log estruturado e NÃO-vazamento de credencial.

Roda OFFLINE (prompt §6): o caminho de SUCESSO real (conexão ao banco) vive em
``tests/integration/test_keep_alive.py`` (@db). Aqui validamos a degradação
controlada em falha, os campos do log e o contrato de exit code — sem Supabase.
"""

import json
from datetime import UTC, datetime

import pytest
from src.infrastructure.config import Settings
from src.tasks import keep_alive
from src.tasks.keep_alive import KeepAliveOutcome, _error_fields, _ok_fields, run

# Senha reconhecível: os testes provam que ela NÃO aparece em log algum.
_SENHA_SECRETA = "sup3r-s3cr3t-pw"
# Porta 9 (discard): conexão recusada de imediato, sem DNS nem timeout longo.
_URL_INALCANCAVEL = f"postgresql+asyncpg://postgres:{_SENHA_SECRETA}@127.0.0.1:9/nada"


def _settings(url: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=url,
        migrations_database_url=url,
    )


def _ultima_linha_json(captured: str) -> dict[str, object]:
    linhas = [ln for ln in captured.strip().splitlines() if ln.strip()]
    assert linhas, "esperava ao menos uma linha de log em stdout"
    return dict(json.loads(linhas[-1]))


class TestCamposDeLog:
    """Contrato dos campos do evento keep_alive (prompt §4.1.3 / §6)."""

    def test_ok_fields_tem_o_contrato_completo(self) -> None:
        outcome = KeepAliveOutcome(
            db_time=datetime(2026, 6, 11, 9, 0, tzinfo=UTC), latency_ms=12.34
        )
        assert _ok_fields(outcome, "cid-123", "production") == {
            "event": "keep_alive",
            "status": "ok",
            "latency_ms": 12.34,
            "db_time": "2026-06-11T09:00:00+00:00",
            "correlation_id": "cid-123",
            "env": "production",
        }

    def test_error_fields_so_expoe_o_tipo_da_excecao(self) -> None:
        # str(exc) contém "password" de propósito: provamos que NÃO entra no log.
        exc = ConnectionRefusedError("falha: host=db password=topsecret")
        fields = _error_fields(exc, "cid-9", "production")
        assert fields == {
            "event": "keep_alive",
            "status": "error",
            "correlation_id": "cid-9",
            "env": "production",
            "error_type": "ConnectionRefusedError",
        }
        assert "password" not in json.dumps(fields)
        assert "topsecret" not in json.dumps(fields)


class TestExecucaoOffline:
    def test_falha_retorna_exit_1_e_loga_error_sem_vazar_credencial(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = run(_settings(_URL_INALCANCAVEL))

        assert code == 1
        captured = capsys.readouterr().out
        evento = _ultima_linha_json(captured)
        assert evento["event"] == "keep_alive"
        assert evento["status"] == "error"
        assert evento["correlation_id"]
        assert evento["env"] == "test"
        assert "error_type" in evento
        # CRÍTICO (§4.1.5): a senha não pode vazar em NENHUM ponto do stdout.
        assert _SENHA_SECRETA not in captured

    def test_sucesso_simulado_retorna_exit_0_e_loga_contrato_completo(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        outcome = KeepAliveOutcome(db_time=datetime(2026, 6, 11, 9, 0, tzinfo=UTC), latency_ms=7.5)

        async def fake_run_keep_alive(settings: Settings) -> KeepAliveOutcome:
            return outcome

        monkeypatch.setattr(keep_alive, "run_keep_alive", fake_run_keep_alive)

        code = run(_settings(_URL_INALCANCAVEL))

        assert code == 0
        evento = _ultima_linha_json(capsys.readouterr().out)
        assert evento["event"] == "keep_alive"
        assert evento["status"] == "ok"
        assert evento["latency_ms"] == 7.5
        assert evento["db_time"] == "2026-06-11T09:00:00+00:00"
        assert evento["correlation_id"]
        assert evento["env"] == "test"

    def test_main_delega_para_run_com_settings_do_ambiente(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chamado_com: dict[str, Settings] = {}
        sentinela = _settings(_URL_INALCANCAVEL)

        def fake_run(settings: Settings) -> int:
            chamado_com["settings"] = settings
            return 0

        monkeypatch.setattr(keep_alive, "get_settings", lambda: sentinela)
        monkeypatch.setattr(keep_alive, "run", fake_run)

        assert keep_alive.main() == 0
        assert chamado_com["settings"] is sentinela

    def test_main_falha_de_config_retorna_1_sem_vazar_credencial(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """W0-A-005: um Settings inválido (URL malformada com credencial)
        carregado em main() vira exit 1 + log só com error_type — sem traceback
        cru nem connection string em stdout."""

        def get_settings_invalido() -> Settings:
            # mesma falha de um KEEPALIVE_DATABASE_URL malformado com credencial
            return Settings(
                _env_file=None,  # type: ignore[call-arg]
                database_url=f"mysql://user:{_SENHA_SECRETA}@host:3306/db",
                migrations_database_url=_URL_INALCANCAVEL,
            )

        monkeypatch.setattr(keep_alive, "get_settings", get_settings_invalido)

        code = keep_alive.main()

        assert code == 1
        captured = capsys.readouterr().out
        assert _SENHA_SECRETA not in captured
        evento = _ultima_linha_json(captured)
        assert evento["status"] == "error"
        assert "error_type" in evento
