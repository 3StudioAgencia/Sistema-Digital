"""Fixtures compartilhadas da suíte.

Princípios (prompt W0-C01 §6):
- A suíte roda OFFLINE: nada aqui exige Supabase, R2 ou rede externa.
- Testes que exigem Postgres usam a fixture ``database_url``: skip local
  quando o banco não está acessível; FALHA no CI (``REQUIRE_DB_TESTS=1``).
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from src.adapters.inbound.http.app import create_app
from src.adapters.inbound.http.health import DbPing
from src.application.ports.storage import StorageObjectNotFound, StoragePort
from src.infrastructure.config import Settings, coerce_asyncpg_url

DEFAULT_TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/rastreio_test"


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------
class FakeStorage(StoragePort):
    """StoragePort em memória — comportamento espelhado na semântica S3."""

    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy
        self._objects: dict[str, tuple[bytes, str]] = {}

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._objects[key] = (data, content_type)
        return key

    def download(self, key: str) -> bytes:
        if key not in self._objects:
            raise StorageObjectNotFound(key)
        return self._objects[key][0]

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def health(self) -> bool:
        return self.healthy


async def ping_ok() -> bool:
    return True


async def ping_down() -> bool:
    return False


# ---------------------------------------------------------------------------
# Isolamento de estado global
# ---------------------------------------------------------------------------
# Chaves que o Settings lê do ambiente. NÃO inclui TEST_DATABASE_URL nem
# REQUIRE_DB_TESTS — esses gateiam os testes @db e são lidos direto de os.environ.
_SETTINGS_ENV_KEYS = (
    "APP_ENV",
    "LOG_LEVEL",
    "DATABASE_URL",
    "MIGRATIONS_DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_JWT_SECRET",
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "CORS_ALLOWED_ORIGINS",
)


@pytest.fixture(autouse=True)
def _isola_env_do_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticidade total: remove do ambiente do processo TODAS as chaves do
    Settings antes de cada teste (W0-A-012).

    ``Settings(_env_file=None)`` isola apenas o arquivo ``.env``; variáveis
    exportadas no shell do desenvolvedor (R2_*, SUPABASE_*, LOG_LEVEL, ...)
    ainda vazariam para os campos não fixados explicitamente, causando falhas
    espúrias. Testes que precisam de uma variável a definem via
    ``monkeypatch.setenv`` no próprio corpo (executado após este autouse).
    """
    for key in _SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _isola_logging_global() -> Iterator[None]:
    """Impede que a (re)configuração global de logging vaze entre testes.

    Tarefas como o keep-alive (W0-C02) chamam ``configure_logging`` como efeito
    de borda; sem isolamento, os handlers do root trocados por um teste afetariam
    os seguintes. Snapshot + restore por teste mantém a suíte hermética.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    try:
        yield
    finally:
        root.handlers, root.level = handlers, level


# ---------------------------------------------------------------------------
# Configuração / app / client
# ---------------------------------------------------------------------------
@pytest.fixture
def settings() -> Settings:
    """Settings explícito e hermético — ``_env_file=None`` impede que um .env
    local de desenvolvedor vaze para dentro da suíte."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=DEFAULT_TEST_DB_URL,
        migrations_database_url=DEFAULT_TEST_DB_URL,
    )


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


def make_client(settings: Settings, storage: StoragePort, db_ping: DbPing) -> httpx.AsyncClient:
    """Client httpx falando direto com a app via ASGI (sem rede)."""
    app = create_app(settings=settings, storage=storage, db_ping=db_ping)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
async def client(settings: Settings, fake_storage: FakeStorage) -> AsyncIterator[httpx.AsyncClient]:
    """Client padrão: storage ok + banco ok (fakes)."""
    async with make_client(settings, fake_storage, ping_ok) as c:
        yield c


# ---------------------------------------------------------------------------
# Postgres real (testes @db)
# ---------------------------------------------------------------------------
async def _can_connect(url: str) -> bool:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return False
    finally:
        await engine.dispose()
    return True


@pytest.fixture(scope="session")
def database_url() -> str:
    """URL do Postgres de teste; faz o gate de disponibilidade uma única vez."""
    url = coerce_asyncpg_url(os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB_URL))
    if not asyncio.run(_can_connect(url)):
        if os.environ.get("REQUIRE_DB_TESTS") == "1":
            pytest.fail(f"REQUIRE_DB_TESTS=1, mas o Postgres de teste não está acessível em {url}")
        pytest.skip(
            "Postgres de teste indisponível — suba com `docker compose up -d db` "
            "para rodar os testes marcados com @db"
        )
    return url
