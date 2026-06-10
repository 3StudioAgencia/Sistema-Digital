"""Correlação por request_id (RNF-024) e tratamento de erros sem vazar stack trace."""

import logging

import httpx
import pytest
from src.adapters.inbound.http.app import create_app
from src.infrastructure.config import Settings

from tests.conftest import FakeStorage, ping_ok


class TestRequestId:
    async def test_resposta_inclui_header_de_correlacao(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        assert response.headers.get("X-Request-ID")

    async def test_header_recebido_e_propagado_de_volta(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health", headers={"X-Request-ID": "id-do-proxy-123"})
        assert response.headers["X-Request-ID"] == "id-do-proxy-123"

    async def test_mesmo_id_aparece_no_log_da_requisicao(
        self, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="rastreio.http"):
            response = await client.get("/health", headers={"X-Request-ID": "corr-42"})

        access_logs = [r for r in caplog.records if r.message == "request completed"]
        assert len(access_logs) == 1
        registro = access_logs[0]
        assert registro.request_id == "corr-42"  # type: ignore[attr-defined]
        assert registro.method == "GET"  # type: ignore[attr-defined]
        assert registro.path == "/health"  # type: ignore[attr-defined]
        assert registro.status_code == response.status_code  # type: ignore[attr-defined]


class TestErroNaoTratado:
    @pytest.fixture
    async def client_com_rota_explosiva(
        self, settings: Settings, fake_storage: FakeStorage
    ) -> httpx.AsyncClient:
        app = create_app(settings=settings, storage=fake_storage, db_ping=ping_ok)

        @app.get("/boom")
        async def boom() -> None:
            raise RuntimeError("segredo interno: senha=hunter2")

        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def test_erro_vira_500_padronizado_sem_stack_trace(
        self,
        client_com_rota_explosiva: httpx.AsyncClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.CRITICAL, logger="rastreio.http.errors"):
            async with client_com_rota_explosiva as client:
                response = await client.get("/boom", headers={"X-Request-ID": "corr-err-7"})

        # Resposta: envelope padronizado, correlacionada, sem vazar detalhes internos
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "internal_error"
        assert body["error"]["request_id"] == "corr-err-7"
        assert "hunter2" not in response.text
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text
        assert response.headers["X-Request-ID"] == "corr-err-7"

        # Log: CRITICAL, correlacionado, com a exceção completa para diagnóstico
        criticos = [r for r in caplog.records if r.levelno == logging.CRITICAL]
        assert len(criticos) == 1
        assert criticos[0].request_id == "corr-err-7"  # type: ignore[attr-defined]
        assert criticos[0].exc_info is not None

    async def test_500_cross_origin_sai_com_headers_cors(
        self, client_com_rota_explosiva: httpx.AsyncClient
    ) -> None:
        """Regressão: o catch-all fica INTERNO ao CORS — sem os headers CORS o
        frontend cross-origin veria erro de rede opaco e perderia o request_id."""
        async with client_com_rota_explosiva as client:
            response = await client.get("/boom", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 500
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "x-request-id" in response.headers
        assert response.json()["error"]["code"] == "internal_error"

    async def test_rede_de_seguranca_do_request_id_middleware(self) -> None:
        """Exceção que escapasse ENTRE os middlewares (ex.: no próprio CORS)
        ainda vira envelope 500 correlacionado — exercita o except do
        RequestIdMiddleware montando uma app SEM o ErrorHandlingMiddleware."""
        from fastapi import FastAPI
        from src.adapters.inbound.http.middleware import RequestIdMiddleware

        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)

        @app.get("/boom")
        async def boom() -> None:
            raise RuntimeError("falha entre middlewares")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            response = await client.get("/boom", headers={"X-Request-ID": "corr-net-1"})

        assert response.status_code == 500
        assert response.json()["error"]["request_id"] == "corr-net-1"
        assert response.headers["X-Request-ID"] == "corr-net-1"

    async def test_handler_de_ultima_instancia_produz_o_mesmo_envelope(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Rede de segurança (exceção fora do alcance do middleware) — chamada direta."""
        from src.adapters.inbound.http.errors import _last_resort_handler
        from starlette.requests import Request

        request = Request(
            {"type": "http", "method": "GET", "path": "/fora-do-middleware", "headers": []}
        )
        with caplog.at_level(logging.CRITICAL, logger="rastreio.http.errors"):
            response = await _last_resort_handler(request, RuntimeError("falha externa"))

        assert response.status_code == 500
        assert b"internal_error" in response.body
        assert any(r.levelno == logging.CRITICAL for r in caplog.records)

    async def test_http_404_usa_o_mesmo_envelope(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/rota-inexistente")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "http_error"

    async def test_payload_invalido_retorna_422_com_detalhes_seguros(
        self, settings: Settings, fake_storage: FakeStorage
    ) -> None:
        app = create_app(settings=settings, storage=fake_storage, db_ping=ping_ok)

        @app.get("/eco/{numero}")
        async def eco(numero: int) -> dict[str, int]:
            return {"numero": numero}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/eco/nao-e-numero")

        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "validation_error"
        assert body["details"][0]["loc"] == ["path", "numero"]
