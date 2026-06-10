"""Settings: carga por ambiente, validação na inicialização e coerções."""

import pytest
from pydantic import ValidationError
from src.infrastructure.config import Settings

PG = "postgresql+asyncpg://user:pass@host:6543/db"
PG_DIRECT = "postgresql+asyncpg://user:pass@host:5432/db"


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": PG,
        "migrations_database_url": PG_DIRECT,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type, call-arg]


class TestCargaPorAmbiente:
    def test_carrega_variaveis_do_ambiente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "staging")
        monkeypatch.setenv("DATABASE_URL", PG)
        monkeypatch.setenv("MIGRATIONS_DATABASE_URL", PG_DIRECT)
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        s = Settings(_env_file=None)  # type: ignore[call-arg]

        assert s.app_env == "staging"
        assert s.database_url == PG
        assert s.migrations_database_url == PG_DIRECT
        assert s.log_level == "DEBUG"

    def test_campos_obrigatorios_ausentes_falham_na_inicializacao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("MIGRATIONS_DATABASE_URL", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)  # type: ignore[call-arg]

        faltantes = {e["loc"][0] for e in exc_info.value.errors()}
        assert {"database_url", "migrations_database_url"} <= faltantes


class TestValidacaoDeUrls:
    def test_coercao_para_driver_asyncpg(self) -> None:
        s = _settings(database_url="postgresql://u:p@h:6543/db")
        assert s.database_url == "postgresql+asyncpg://u:p@h:6543/db"

    def test_coercao_do_esquema_curto_postgres(self) -> None:
        s = _settings(database_url="postgres://u:p@h:6543/db")
        assert s.database_url.startswith("postgresql+asyncpg://")

    def test_url_nao_postgres_rejeitada(self) -> None:
        with pytest.raises(ValidationError):
            _settings(database_url="mysql://u:p@h/db")


class TestR2TudoOuNada:
    def test_sem_r2_e_valido_e_nao_configurado(self) -> None:
        assert _settings().r2_configured is False

    def test_r2_completo_e_configurado(self) -> None:
        s = _settings(
            r2_endpoint_url="https://acc.r2.cloudflarestorage.com",
            r2_access_key_id="key",
            r2_secret_access_key="secret",
            r2_bucket="artes",
        )
        assert s.r2_configured is True

    def test_r2_parcial_falha_rapido(self) -> None:
        with pytest.raises(ValidationError, match="Configuração parcial do R2"):
            _settings(r2_bucket="artes")


class TestCors:
    def test_origens_separadas_por_virgula(self) -> None:
        s = _settings(cors_allowed_origins="http://a.com, http://b.com ,,http://c.com")
        assert s.cors_origins == ["http://a.com", "http://b.com", "http://c.com"]
