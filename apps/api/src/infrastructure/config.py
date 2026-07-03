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


def coerce_asyncpg_url(url: str) -> str:
    """Normaliza URLs Postgres para o driver async usado pelo runtime.

    Supabase/ferramentas costumam fornecer ``postgres://`` ou ``postgresql://``;
    o SQLAlchemy async exige o sufixo de driver ``postgresql+asyncpg://``.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def to_asyncpg_dsn(url: str) -> str:
    """DSN aceito pelo ``asyncpg.connect()`` a partir de uma URL do SQLAlchemy.

    Inverso de ``coerce_asyncpg_url``: o ``asyncpg`` cru NÃO entende o sufixo de
    driver ``+asyncpg`` (só ``postgresql://``/``postgres://``). Usado pelo listener
    de ``LISTEN/NOTIFY`` (etapa 3 da migração), que abre uma conexão asyncpg
    dedicada FORA do engine SQLAlchemy. As URLs do Settings já são normalizadas
    para ``postgresql+asyncpg://`` (``_validate_pg_url``).
    """
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


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

    # --- Auth própria: JWT ES256 emitido pela app (autenticação local) -------
    # Par de chaves EC P-256 em BASE64 do PEM (linha única — evita PEM multilinha
    # em .env). A privada é SERVER-ONLY (assina); a pública verifica (backend e,
    # na Fase 3, o proxy do Next). Sem o par, a app recusa subir (fail-fast) fora
    # de dev/test — ver ``exigir_auth_configurada``.
    auth_jwt_private_key: SecretStr | None = None
    auth_jwt_public_key: str | None = None
    # Emissor (claim ``iss``) dos tokens próprios — validado na verificação.
    auth_issuer: str = "rastreio-api"
    # TTL do access token (curto) e do refresh token rotativo (mais longo).
    auth_access_ttl_seconds: int = 1800  # 30 min
    auth_refresh_ttl_seconds: int = 604800  # 7 dias

    # --- Storage de artes (destino: snapshot no servidor local) ----------
    # Substitui o R2 (migração on-prem): diretório onde a app GRAVA a cópia da arte
    # de cada prova. Opcional no boot — sem ele a app sobe e o readiness reporta
    # storage "down" (degradação clara, sem crash). Ex.: C:\rastreio\artes ou /var/rastreio/artes
    storage_dir: str | None = None

    # --- Servidor de arquivos de artes (FONTE read-only do estúdio) ------
    # Base do share onde as artes vivem, até o STUDIO_TRANSICAO (a app compõe
    # /<COD_VEND_FAT>/<COD_CLIEN>/<COD_REQ_ART>/VERSAO/). SOMENTE LEITURA. Opcional no
    # boot (readiness reporta "down"). Ex.: \\172.16.0.6\Artes\STUDIO_TRANSICAO
    arte_share_base: str | None = None
    # Teto de tamanho da imagem lida do share (guarda anti-OOM; o share é confiável,
    # então é generoso). Acima disso a criação bloqueia com "arte indisponível".
    arte_fonte_tamanho_maximo_mb: int = 50

    # --- ERP legado (Firebird) — SOMENTE LEITURA -------------------------
    # Lê o requerimento de arte (nome/cliente/vendedor + caminho da imagem) para
    # originar a prova. NUNCA escreve (regra do projeto). Opcional no boot (como o
    # R2): sem ele a app sobe e o readiness reporta o ERP "down". ``database`` é a
    # string de conexão do driver (ex.: ``localhost:C:\bancos\STUDIOEART_2010.FDB``);
    # ``client_library`` aponta a ``fbclient.dll`` do servidor instalado (opcional —
    # o driver autolocaliza quando ausente).
    firebird_database: str | None = None
    firebird_user: str | None = None
    firebird_password: SecretStr | None = None
    firebird_charset: str = "WIN1252"
    firebird_client_library: str | None = None

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
        coerced = coerce_asyncpg_url(value)
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

    @field_validator("arte_fonte_tamanho_maximo_mb")
    @classmethod
    def _validate_arte_fonte_teto(cls, value: int) -> int:
        if value <= 0:
            msg = "ARTE_FONTE_TAMANHO_MAXIMO_MB deve ser um inteiro positivo (MB)."
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_firebird_all_or_nothing(self) -> Self:
        """Firebird parcialmente configurado é erro de operação — falhe rápido
        (mesmo princípio do R2). ``charset``/``client_library`` têm default/são
        opcionais; o trio conexão é tudo-ou-nada."""
        provided = [self.firebird_database, self.firebird_user, self.firebird_password]
        if any(v is not None for v in provided) and not all(v is not None for v in provided):
            msg = (
                "Configuração parcial do Firebird: defina FIREBIRD_DATABASE, "
                "FIREBIRD_USER e FIREBIRD_PASSWORD juntos, ou nenhum deles."
            )
            raise ValueError(msg)
        return self

    @property
    def storage_configured(self) -> bool:
        return self.storage_dir is not None

    @property
    def arte_fonte_configured(self) -> bool:
        return self.arte_share_base is not None

    @property
    def arte_fonte_tamanho_maximo_bytes(self) -> int:
        return self.arte_fonte_tamanho_maximo_mb * 1024 * 1024

    @property
    def firebird_configured(self) -> bool:
        return self.firebird_database is not None

    @property
    def auth_configured(self) -> bool:
        """Emissão/verificação de token utilizável: precisa do par de chaves ES256."""
        return self.auth_jwt_private_key is not None and self.auth_jwt_public_key is not None

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
