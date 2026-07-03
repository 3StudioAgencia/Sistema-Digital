"""Health checks (RNF-024): liveness imediato; readiness com status por dependência.

Roda offline — banco e storage são fakes injetados via app factory.
"""

import logging

import httpx
import pytest
from src.infrastructure.config import APP_VERSION, Settings

from tests.conftest import FakeStorage, make_client, ping_down, ping_ok


class TestLiveness:
    async def test_responde_200_sem_tocar_dependencias(
        self, settings: Settings, fake_storage: FakeStorage
    ) -> None:
        # storage e banco DOWN: liveness não pode ser afetada por dependências
        async with make_client(settings, FakeStorage(healthy=False), ping_down) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestReadiness:
    async def test_tudo_ok_retorna_200_com_estrutura_completa(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> None:
        response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "status": "ok",
            "checks": {"database": "ok", "storage": "ok", "erp": "ok", "arte_fonte": "ok"},
            "version": APP_VERSION,
            "env": settings.app_env,
        }

    async def test_deps_de_criacao_down_nao_bloqueiam_readiness(
        self, settings: Settings, fake_storage: FakeStorage
    ) -> None:
        """ERP (Firebird) e servidor de arquivos de artes são dependências só da
        CRIAÇÃO de provas por requerimento: a queda é REPORTADA (``down``) mas NÃO
        derruba a API (200, status 'ok') — reads/dashboard/auth seguem. Sem
        ``requerimento_reader``/``arte_fonte``, os stand-ins inertes reportam False."""
        async with make_client(settings, fake_storage, ping_ok) as client:
            response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"] == {
            "database": "ok",
            "storage": "ok",
            "erp": "down",
            "arte_fonte": "down",
        }

    async def test_storage_down_retorna_503_reportando_so_o_storage(
        self, settings: Settings
    ) -> None:
        async with make_client(settings, FakeStorage(healthy=False), ping_ok) as client:
            response = await client.get("/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"]["storage"] == "down"
        assert body["checks"]["database"] == "ok"

    async def test_banco_down_retorna_503_reportando_so_o_banco(
        self, settings: Settings, fake_storage: FakeStorage
    ) -> None:
        async with make_client(settings, fake_storage, ping_down) as client:
            response = await client.get("/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["checks"]["database"] == "down"
        assert body["checks"]["storage"] == "ok"

    async def test_ping_que_levanta_excecao_vira_down_sem_derrubar_a_app(
        self, settings: Settings, fake_storage: FakeStorage, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def ping_explosivo() -> bool:
            raise ConnectionError("conexão recusada")

        with caplog.at_level(logging.WARNING, logger="rastreio.http.health"):
            async with make_client(settings, fake_storage, ping_explosivo) as client:
                response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["database"] == "down"
        # W0-A-003: a falha do check deixa rastro diagnóstico (RNF-024)
        avisos = [r for r in caplog.records if r.name == "rastreio.http.health"]
        assert avisos and getattr(avisos[0], "dependency", None) == "database"
        assert getattr(avisos[0], "error_type", None) == "ConnectionError"

    async def test_storage_que_levanta_excecao_vira_down_sem_derrubar_a_app(
        self, settings: Settings, caplog: pytest.LogCaptureFixture
    ) -> None:
        class StorageExplosivo(FakeStorage):
            def health(self) -> bool:
                raise ConnectionError("endpoint inacessível")

        with caplog.at_level(logging.WARNING, logger="rastreio.http.health"):
            async with make_client(settings, StorageExplosivo(), ping_ok) as client:
                response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["storage"] == "down"
        avisos = [r for r in caplog.records if r.name == "rastreio.http.health"]
        assert avisos and getattr(avisos[0], "dependency", None) == "storage"
