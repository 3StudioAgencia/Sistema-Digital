"""Settings: carga por ambiente, validação na inicialização e coerções."""

import os

import pytest
from pydantic import ValidationError
from src.infrastructure.config import Settings

from tests.conftest import _SETTINGS_ENV_KEYS

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

    def test_validation_error_nao_ecoa_a_connection_string(self) -> None:
        """W0-A-005: hide_input_in_errors impede que a URL rejeitada (com
        credencial) apareça no texto da ValidationError."""
        senha = "sup3r-s3cr3t-pw"
        with pytest.raises(ValidationError) as exc_info:
            _settings(database_url=f"mysql://user:{senha}@host:3306/db")
        assert senha not in str(exc_info.value)


class TestStorageEArteFonte:
    def test_sem_storage_nem_share_e_valido_e_nao_configurado(self) -> None:
        s = _settings()
        assert s.storage_configured is False
        assert s.arte_fonte_configured is False

    def test_storage_e_share_configurados(self) -> None:
        s = _settings(
            storage_dir="/var/rastreio/artes",
            arte_share_base=r"\\host\Artes\STUDIO_TRANSICAO",
        )
        assert s.storage_configured is True
        assert s.arte_fonte_configured is True

    def test_teto_da_fonte_padrao_50mb(self) -> None:
        assert _settings().arte_fonte_tamanho_maximo_bytes == 50 * 1024 * 1024

    def test_teto_da_fonte_nao_positivo_falha_rapido(self) -> None:
        with pytest.raises(ValidationError, match="ARTE_FONTE_TAMANHO_MAXIMO_MB"):
            _settings(arte_fonte_tamanho_maximo_mb=0)


class TestCors:
    def test_origens_separadas_por_virgula(self) -> None:
        s = _settings(cors_allowed_origins="http://a.com, http://b.com ,,http://c.com")
        assert s.cors_origins == ["http://a.com", "http://b.com", "http://c.com"]

    def test_origem_curinga_rejeitada(self) -> None:
        """W0-A-015: '*' + credentials refletiria qualquer origem — proibido."""
        with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
            _settings(cors_allowed_origins="https://app.exemplo.com, *")


class TestLogLevel:
    def test_normaliza_caixa_e_espacos(self) -> None:
        assert _settings(log_level="  debug ").log_level == "DEBUG"

    def test_nivel_invalido_falha_no_boot_citando_a_variavel(self) -> None:
        # W0-A-013: antes, LOG_LEVEL inválido só estourava em configure_logging
        with pytest.raises(ValidationError, match="LOG_LEVEL"):
            _settings(log_level="VERBOSE")


class TestHermeticidade:
    def test_chaves_do_settings_nao_vazam_do_shell(self) -> None:
        """W0-A-012: o autouse de conftest limpa toda chave do Settings — a
        suíte não depende do ambiente local nem do shell do CI (que exporta
        DATABASE_URL/MIGRATIONS_DATABASE_URL no job)."""
        presentes = [k for k in _SETTINGS_ENV_KEYS if k in os.environ]
        assert not presentes, f"chaves do Settings vazaram do ambiente: {presentes}"
