# apps/api — Backend FastAPI

Backend do Sistema de Rastreio de Provas Digitais, em **arquitetura hexagonal**
(Ports & Adapters — `CLAUDE.md §5`). Python 3.12 · FastAPI · SQLAlchemy 2.0 async ·
Pydantic v2 · Alembic · boto3 (R2). Gerenciado por **uv** (ADR-010).

## Camadas

| Pasta | Papel | Pode importar |
| --- | --- | --- |
| `src/domain/` | Regras de negócio puras (waves 2+) | nada de fora do domain |
| `src/application/` | Casos de uso + **portas** (`StoragePort`, `UnitOfWork`) | domain |
| `src/adapters/inbound/http/` | Routers, middleware de request-id, erros, health | application, infrastructure |
| `src/adapters/outbound/` | Implementações das portas (R2/boto3; DB na Wave 2) | application, infrastructure |
| `src/infrastructure/` | `config.py`, `logging.py`, `database.py` | — |
| `src/main.py` | **Composition root** — único ponto de wiring | tudo |

## Comandos

```bash
uv sync                                   # instalar dependências (lockfile pinado)
uv run uvicorn src.main:app --reload      # dev server → http://localhost:8000/docs
uv run alembic upgrade head               # aplicar migrations (usa MIGRATIONS_DATABASE_URL)
uv run pytest --cov                       # testes + cobertura (suíte roda offline; ver abaixo)
uv run ruff check . && uv run mypy        # lint + tipos (strict)
```

## Conexões com o banco (ADR-007)

- **Runtime** (`DATABASE_URL`): pooler de transação do Supabase (porta **6543**) —
  `NullPool` + caches de prepared statement desligados (PgBouncer transaction mode).
- **Migrations** (`MIGRATIONS_DATABASE_URL`): conexão direta (porta **5432**).
- Em dev local (`docker compose up -d db`) ambas apontam para o Postgres local.

## Testes

- A suíte **roda offline**: storage testado com `moto`/fake; health com fakes injetados.
- Testes marcados `@pytest.mark.db` exigem Postgres acessível (`TEST_DATABASE_URL`,
  default `postgresql+asyncpg://postgres:postgres@localhost:5432/rastreio_test`).
  Sem banco eles fazem **skip** local; no CI `REQUIRE_DB_TESTS=1` transforma skip em falha.

## Observabilidade (RNF-024)

- Logs **JSON estruturados** em stdout, com `request_id` em todo registro da requisição.
- Toda resposta HTTP carrega o header `X-Request-ID` (gerado ou propagado).
- `GET /health` (liveness) · `GET /health/ready` (readiness com status por dependência).
- Erros não tratados → log `CRITICAL` correlacionado + envelope JSON `500` sem stack trace.
