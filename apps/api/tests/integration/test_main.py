"""Composition root (src/main.py): a app sobe a partir de variáveis de ambiente.

Roda offline: sem R2 a app usa o UnconfiguredStorage; o ciclo de vida
(startup/shutdown via TestClient) apenas loga e descarta o engine.
"""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from src.adapters.outbound.storage.r2_storage import R2Storage
from src.adapters.outbound.storage.unconfigured import UnconfiguredStorage
from src.infrastructure.config import get_settings

PG_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/rastreio_test"


@pytest.fixture(autouse=True)
def _ambiente_minimo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> object:
    """Ambiente limpo e determinístico para cada teste (sem vazar .env local)."""
    get_settings.cache_clear()
    # Settings lê `.env` RELATIVO ao CWD; rodar de um diretório vazio garante
    # hermeticidade mesmo com um `.env` real preenchido em apps/api (R2/Supabase
    # configurados na validação do C01). delenv só cobre o ambiente do processo,
    # não o arquivo — daí o chdir.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    monkeypatch.setenv("MIGRATIONS_DATABASE_URL", PG_URL)
    for var in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(var, raising=False)
    yield
    get_settings.cache_clear()


@pytest.fixture
def build_app() -> Callable[[], FastAPI]:
    """Import lazy de src.main: o módulo constrói a app no import (para o
    uvicorn), então só pode ser importado DEPOIS de o ambiente estar definido."""
    from src.main import build_app as factory

    return factory


async def test_app_sobe_sem_r2_com_storage_nao_configurado(
    build_app: Callable[[], FastAPI],
) -> None:
    app = build_app()

    assert isinstance(app.state.storage, UnconfiguredStorage)
    assert app.state.settings.app_env == "test"

    # lifespan explícito: exercita startup/shutdown (log + dispose do engine)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_app_usa_r2_quando_configurado(
    build_app: Callable[[], FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://conta-exemplo.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "chave-exemplo")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "segredo-exemplo")
    monkeypatch.setenv("R2_BUCKET", "artes")

    app = build_app()

    # Só a SELEÇÃO do adapter é validada — nenhuma chamada de rede acontece aqui
    assert isinstance(app.state.storage, R2Storage)


async def test_docs_openapi_expostos(build_app: Callable[[], FastAPI]) -> None:
    app = build_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            assert (await client.get("/docs")).status_code == 200
            schema = (await client.get("/openapi.json")).json()

    assert schema["info"]["title"] == "rastreio-api"
    assert "/health/ready" in schema["paths"]
