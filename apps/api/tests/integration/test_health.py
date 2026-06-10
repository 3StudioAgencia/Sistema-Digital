"""Health checks (RNF-024): liveness imediato; readiness com status por dependência.

Roda offline — banco e storage são fakes injetados via app factory.
"""

import httpx
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
            "checks": {"database": "ok", "storage": "ok"},
            "version": APP_VERSION,
            "env": settings.app_env,
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
        self, settings: Settings, fake_storage: FakeStorage
    ) -> None:
        async def ping_explosivo() -> bool:
            raise ConnectionError("conexão recusada")

        async with make_client(settings, fake_storage, ping_explosivo) as client:
            response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["database"] == "down"

    async def test_storage_que_levanta_excecao_vira_down_sem_derrubar_a_app(
        self, settings: Settings
    ) -> None:
        class StorageExplosivo(FakeStorage):
            def health(self) -> bool:
                raise ConnectionError("endpoint inacessível")

        async with make_client(settings, StorageExplosivo(), ping_ok) as client:
            response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["storage"] == "down"
