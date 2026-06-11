"""Configuração por ambiente (pydantic-settings).

Princípios (prompt W0-C01 §3.4 / CLAUDE.md §9):
- Segredos SÓ via variáveis de ambiente — nenhum default sensível no código.
- Validação na inicialização: ambiente mal configurado falha rápido no boot,
  nunca em runtime no meio de uma requisição.
- ``.env`` é lido apenas como conveniência local; em staging/produção as
  variáveis vêm do orquestrador (CI/host).
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "rastreio-api"
APP_VERSION = "0.1.0"

AppEnv = Literal["dev", "test", "staging", "production"]

# Níveis de log aceitos (contrato documentado em .env.example). Validados no
# boot para falhar rápido com mensagem nomeando a variável (W0-A-013).
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _coerce_asyncpg_url(url: str) -> str:
    """Normaliza URLs Postgres para o driver async usado pelo runtime.

    Supabase/ferramentas costumam fornecer ``postgres://`` ou ``postgresql://``;
    o SQLAlchemy async exige o sufixo de driver ``postgresql+asyncpg://``.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    """Fonte única de configuração do backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Uma ValidationError do Pydantic v2 imprime input_value='<valor>' por
        # padrão — para uma URL de banco isso ECOA a connection string (com
        # credencial) no traceback. Ocultar a entrada nos erros é defesa em
        # profundidade contra vazamento de segredo (W0-A-005 / CLAUDE.md §9).
        hide_input_in_errors=True,
    )

    # --- Aplicação -------------------------------------------------------
    app_env: AppEnv = "dev"
    log_level: str = "INFO"

    # --- Banco (ADR-007: duas URLs distintas) ----------------------------
    # Runtime: pooler de transação do Supabase (porta 6543) — PgBouncer.
    database_url: str
    # Migrations/Alembic: conexão direta/sessão (porta 5432) — DDL exige sessão.
    migrations_database_url: str

    # --- Supabase (previsto para a Wave 1/C03 — apenas documentado) ------
    supabase_url: str | None = None
    supabase_jwt_secret: SecretStr | None = None

    # --- Cloudflare R2 (S3-compatível) -----------------------------------
    # Opcionais por design: o ambiente pode não ter credenciais reais
    # (prompt §3.6). Sem R2 configurado a app sobe e o readiness reporta
    # storage "down" — degradação clara, sem derrubar o processo.
    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket: str | None = None

    # --- HTTP -------------------------------------------------------------
    cors_allowed_origins: str = "http://localhost:3000"

    @field_validator("log_level", mode="before")
    @classmethod
    def _validate_log_level(cls, value: object) -> str:
        """Normaliza (caixa/espaços) e valida o nível no boot — em vez de
        estourar um ``ValueError`` genérico depois, em ``configure_logging``."""
        normalized = str(value).strip().upper()
        if normalized not in _VALID_LOG_LEVELS:
            opcoes = ", ".join(sorted(_VALID_LOG_LEVELS))
            msg = f"LOG_LEVEL inválido: use um de [{opcoes}]"
            raise ValueError(msg)
        return normalized

    @field_validator("database_url", "migrations_database_url")
    @classmethod
    def _validate_pg_url(cls, value: str) -> str:
        coerced = _coerce_asyncpg_url(value)
        if not coerced.startswith("postgresql+asyncpg://"):
            msg = "URL de banco deve ser PostgreSQL (postgresql://... ou postgresql+asyncpg://...)"
            raise ValueError(msg)
        return coerced

    @field_validator("cors_allowed_origins")
    @classmethod
    def _reject_wildcard_cors(cls, value: str) -> str:
        """Proíbe origem curinga no CORS (W0-A-015).

        A app envia ``Access-Control-Allow-Credentials: true``; com ``"*"`` o
        Starlette **reflete** a Origin do request — qualquer site leria respostas
        autenticadas. A app sempre conhece suas origens, então exigi-las
        explícitas é seguro e falha rápido contra má configuração (mesmo
        princípio do validador tudo-ou-nada do R2)."""
        origens = [o.strip() for o in value.split(",") if o.strip()]
        if "*" in origens:
            msg = (
                "CORS_ALLOWED_ORIGINS não pode conter '*' (a API usa credentials): "
                "liste as origens explicitamente."
            )
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_r2_all_or_nothing(self) -> Self:
        """R2 parcialmente configurado é quase sempre erro de operação — falhe rápido."""
        provided = [
            self.r2_endpoint_url,
            self.r2_access_key_id,
            self.r2_secret_access_key,
            self.r2_bucket,
        ]
        if any(v is not None for v in provided) and not all(v is not None for v in provided):
            msg = (
                "Configuração parcial do R2: defina TODAS as variáveis "
                "R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY e R2_BUCKET "
                "ou nenhuma delas."
            )
            raise ValueError(msg)
        return self

    @property
    def r2_configured(self) -> bool:
        return self.r2_bucket is not None

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Instância única por processo (backend stateless: config é imutável).

    ``lru_cache`` evita reler/revalidar env a cada uso; testes constroem
    ``Settings(...)`` diretamente e nunca dependem deste cache.
    """
    return Settings()  # type: ignore[call-arg]  # campos obrigatórios vêm do ambiente
