"""Logging estruturado JSON com correlação por request_id (RNF-024)."""

import json
import logging

import pytest
from src.infrastructure.logging import RequestIdFilter, configure_logging, request_id_var


@pytest.fixture(autouse=True)
def _restaura_logging() -> object:
    """Garante que a configuração global de logging não vaza entre testes."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level


def _ultima_linha_json(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    linhas = [ln for ln in capsys.readouterr().out.strip().splitlines() if ln.strip()]
    return dict(json.loads(linhas[-1]))


class TestConfigureLogging:
    def test_saida_e_json_estruturado_com_campos_canonicos(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configure_logging("INFO")
        logging.getLogger("rastreio.teste").info("evento de teste", extra={"detalhe": 42})

        registro = _ultima_linha_json(capsys)
        assert registro["message"] == "evento de teste"
        assert registro["level"] == "INFO"
        assert registro["logger"] == "rastreio.teste"
        assert registro["detalhe"] == 42
        assert "timestamp" in registro

    def test_request_id_do_contexto_aparece_em_qualquer_logger(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configure_logging("INFO")
        token = request_id_var.set("ctx-abc-123")
        try:
            logging.getLogger("qualquer.modulo").warning("algo aconteceu")
        finally:
            request_id_var.reset(token)

        assert _ultima_linha_json(capsys)["request_id"] == "ctx-abc-123"

    def test_fora_de_request_o_id_e_nulo(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging("INFO")
        logging.getLogger("job.fora.de.request").info("execução de job")
        assert _ultima_linha_json(capsys)["request_id"] is None

    def test_idempotente_nao_acumula_handlers(self) -> None:
        configure_logging("INFO")
        configure_logging("DEBUG")

        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert root.level == logging.DEBUG

    def test_loggers_do_uvicorn_propagam_para_o_root_json(self) -> None:
        configure_logging("INFO")
        for nome in ("uvicorn", "uvicorn.error"):
            assert logging.getLogger(nome).handlers == []
            assert logging.getLogger(nome).propagate is True

    def test_access_log_nativo_do_uvicorn_e_silenciado(self) -> None:
        """O access log da app é o do RequestIdMiddleware (correlacionado);
        o nativo do uvicorn duplicaria a linha e sairia com request_id nulo."""
        configure_logging("INFO")
        access = logging.getLogger("uvicorn.access")
        assert access.handlers == []
        assert access.propagate is False


class TestRequestIdFilter:
    def test_nao_sobrescreve_request_id_explicito(self) -> None:
        record = logging.LogRecord("x", logging.INFO, "f", 1, "m", None, None)
        record.request_id = "explicito"
        token = request_id_var.set("do-contexto")
        try:
            assert RequestIdFilter().filter(record) is True
        finally:
            request_id_var.reset(token)
        assert record.request_id == "explicito"
