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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from src.adapters.inbound.http.app import create_app
from src.adapters.inbound.http.auth import JwtVerifier
from src.adapters.inbound.http.health import DbPing
from src.application.ports.arte_fonte import ArteFonteError, ArteFontePort, ArteSelecionada
from src.application.ports.password_hasher import PasswordHasherPort
from src.application.ports.requerimentos import RequerimentoReaderPort
from src.application.ports.storage import StorageObjectNotFound, StoragePort
from src.application.ports.tokens import TokenIssuerPort
from src.domain.requerimentos import RequerimentoArte
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


class FakeRequerimentoReader(RequerimentoReaderPort):
    """RequerimentoReaderPort em memória — resolve por ``COD_REQ_ART`` sem ERP real.

    ``erro`` simula ERP indisponível (503): quando definido, ``buscar`` o levanta."""

    def __init__(
        self,
        dados: dict[int, RequerimentoArte] | None = None,
        healthy: bool = True,
    ) -> None:
        self.healthy = healthy
        self._dados = dados or {}
        self.erro: Exception | None = None

    def buscar(self, cod_req_art: int) -> RequerimentoArte | None:
        if self.erro is not None:
            raise self.erro
        return self._dados.get(cod_req_art)

    def health(self) -> bool:
        return self.healthy


class FakeArteFonte(ArteFontePort):
    """ArteFontePort em memória — devolve uma arte fixa, sem tocar disco/share.

    ``erro`` simula share fora do ar / arte indisponível: quando definido,
    ``obter_arte`` o levanta. ``chamadas`` registra os argumentos recebidos."""

    def __init__(self, arte: ArteSelecionada | None = None, healthy: bool = True) -> None:
        self.healthy = healthy
        self._arte = arte
        self.erro: Exception | None = None
        self.chamadas: list[tuple[int, int, int, str | None]] = []

    def obter_arte(
        self,
        cod_vend_fat: int,
        cod_cliente: int,
        cod_req_art: int,
        anexo_imagem: str | None,
    ) -> ArteSelecionada:
        self.chamadas.append((cod_vend_fat, cod_cliente, cod_req_art, anexo_imagem))
        if self.erro is not None:
            raise self.erro
        if self._arte is None:
            raise ArteFonteError("FakeArteFonte sem arte configurada")
        return self._arte

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
    "AUTH_JWT_PRIVATE_KEY",
    "AUTH_JWT_PUBLIC_KEY",
    "AUTH_ISSUER",
    "AUTH_ACCESS_TTL_SECONDS",
    "AUTH_REFRESH_TTL_SECONDS",
    "STORAGE_DIR",
    "ARTE_SHARE_BASE",
    "ARTE_FONTE_TAMANHO_MAXIMO_MB",
    "FIREBIRD_DATABASE",
    "FIREBIRD_USER",
    "FIREBIRD_PASSWORD",
    "FIREBIRD_CHARSET",
    "FIREBIRD_CLIENT_LIBRARY",
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


def make_client(
    settings: Settings,
    storage: StoragePort,
    db_ping: DbPing,
    jwt_verifier: JwtVerifier | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    token_issuer: TokenIssuerPort | None = None,
    system_session_factory: async_sessionmaker[AsyncSession] | None = None,
    password_hasher: PasswordHasherPort | None = None,
    requerimento_reader: RequerimentoReaderPort | None = None,
    arte_fonte: ArteFontePort | None = None,
) -> httpx.AsyncClient:
    """Client httpx falando direto com a app via ASGI (sem rede).

    ``jwt_verifier`` opcional: testes de auth injetam um verifier de teste
    (segredo HS256 conhecido / JWKS dublê); os demais usam o default deny-all.
    ``session_factory``: testes de usuários injetam o Postgres de teste; o default
    (None) faz as rotas de usuários responderem 503. ``token_issuer``/
    ``system_session_factory`` (auth própria): testes de login injetam o emissor
    ES256 de teste + a sessão de sistema; sem eles, ``/auth/login`` responde 503.
    """
    app = create_app(
        settings=settings,
        storage=storage,
        db_ping=db_ping,
        requerimento_reader=requerimento_reader,
        arte_fonte=arte_fonte,
        jwt_verifier=jwt_verifier,
        session_factory=session_factory,
        token_issuer=token_issuer,
        system_session_factory=system_session_factory,
        password_hasher=password_hasher,
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
async def client(settings: Settings, fake_storage: FakeStorage) -> AsyncIterator[httpx.AsyncClient]:
    """Client padrão: storage ok + banco ok + ERP ok + fonte de arte ok (fakes)."""
    async with make_client(
        settings,
        fake_storage,
        ping_ok,
        requerimento_reader=FakeRequerimentoReader(),
        arte_fonte=FakeArteFonte(),
    ) as c:
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
