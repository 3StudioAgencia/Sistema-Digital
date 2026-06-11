# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

> **Convenção:** registre as mudanças em `[Unreleased]`, agrupadas por categoria (*Added, Changed, Deprecated, Removed, Fixed, Security*), referenciando o componente (ex.: `W0-C01`). Ao concluir uma wave ou liberar uma versão, mova o bloco para uma seção versionada com data.

---

## [Unreleased]

### Added
- **W0-C02 (api):** rotina de **keep-alive** do Postgres (`src/tasks/keep_alive.py`, executável por `uv run python -m src.tasks.keep_alive`) — gatilho externo independente do host da API (ADR-015) que faz um `SELECT now()` **read-only** na conexão direta/sessão (5432, `MIGRATIONS_DATABASE_URL`), emite **um log JSON estruturado** (`event="keep_alive"`, `status`, `latency_ms`, `db_time`, `correlation_id`, `env`) e devolve **exit 0/≠0**. Em falha loga só `error_type` (nunca a connection string). A lógica de ida ao banco foi **consolidada** em `fetch_db_time()` (`src/infrastructure/database.py`), reutilizada pelo `ping()` do readiness **e** pelo keep-alive (DRY); novo `create_direct_engine()` para a conexão *one-shot*.
- **W0-C02 (ci):** workflow agendado `.github/workflows/keep-alive.yml` — `schedule` (`0 9 * * *` UTC = 06:00 America/Sao_Paulo) + `workflow_dispatch`, `concurrency` sem sobreposição, `timeout-minutes` curto, `permissions: contents: read`, connection string via secret `KEEPALIVE_DATABASE_URL` e **alerta de falha opcional** via `ALERT_WEBHOOK_URL` (passo `if: failure()`, pulado sem o secret; nada hardcoded).
- **W0-C02 (api/tests):** testes do keep-alive — offline (`tests/unit/test_keep_alive.py`: contrato dos campos do log, exit codes e **prova de não-vazamento de credencial**) e `@db` (`tests/integration/test_keep_alive.py`: sucesso ponta a ponta contra Postgres real). Validado em execução real contra o Supabase (sucesso `exit 0`) e em falha controlada (`exit 1`).
- **W0-C02 (docs):** `docs/keep-alive.md` (por que existe, gatilho externo, cadência e racional, como ligar em produção, teste manual, e a alternativa Cloudflare Worker Cron para hardening de longo prazo); link em `docs/setup-infra.md`. ADR-015 em `DECISIONS.md`.
- **Infra/repo:** projeto publicado no GitHub ([`3studioagn/Sistema-Digital`](https://github.com/3studioagn/Sistema-Digital)) com modelo de branches **gitflow leve** — `main` (estável) + `develop` (integração, padrão); ADR-016 em `DECISIONS.md`.
- **W0-C01:** estrutura do monorepo em Ports & Adapters (`apps/api`, `apps/web`, `docs/`, `.github/`), com `git init`, `.gitignore`, `.editorconfig`, `.gitattributes` e `docker-compose.yml` (Postgres 17 com healthcheck, volume e banco de teste isolado `rastreio_test`).
- **W0-C01 (api):** esqueleto FastAPI hexagonal — `Settings` validado na inicialização (duas URLs de banco, ADR-007; R2 tudo-ou-nada), engine async `NullPool` + caches de prepared statement desligados (PgBouncer transaction mode), `StoragePort` + `R2Storage` (boto3 injetado) + `UnconfiguredStorage`, `UnitOfWork` com ponto de extensão para RLS por request (ADR-008), logging JSON estruturado com `request_id` (`ContextVar` + filtro global), middleware de correlação com access log e catch-all (ADR-013), handlers de erro com envelope padronizado sem stack trace, `GET /health` e `GET /health/ready` (status por dependência, 503 em degradação), app factory + composition root único em `src/main.py`, Dockerfile multi-stage non-root com healthcheck, `.env.example` completo.
- **W0-C01 (api):** Alembic assíncrono via `MIGRATIONS_DATABASE_URL` (conexão direta), migration baseline `0001` (pgcrypto, sem tabelas de domínio) e `migrations/rls/README.md` com a política de versionamento de policies.
- **W0-C01 (api):** suíte com 66 testes (config, storage via moto + fake, health, request-id/erros, composition root, conectividade e ciclo completo do Alembic) — roda offline com skip dos testes `@db`; cobertura 100% da camada; `ruff` + `mypy --strict` verdes. Validada contra PostgreSQL 17.10 real.
- **W0-C01 (web):** scaffolding Next.js 16.2.9 (App Router, TypeScript strict, CSS Modules), página de status que consulta `/health/ready` uma única vez (sem polling), client Supabase mínimo lazy (sem auth — Wave 1), ESLint flat + Prettier, `.env.example`, build hermético (fonte de sistema, `turbopack.root` explícito).
- **W0-C01 (ci/docs):** GitHub Actions com jobs `api` (uv, ruff, mypy, `alembic upgrade`+`downgrade`+`upgrade` contra Postgres 17 service container, pytest com `REQUIRE_DB_TESTS=1`) e `web` (pnpm lint/build); passo de deploy documentado e parametrizável (ADR-009); `docs/setup-infra.md` com provisionamento Supabase/R2 e checklist dos critérios de aceitação.
- Inicialização do projeto: documentos de contexto na raiz (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`).
- Baseline de decisões de arquitetura (ADR-001 a ADR-011) em `DECISIONS.md`; ADR-012 a ADR-014 adicionadas no W0-C01; **ADR-015** (keep-alive externo) no W0-C02.

### Fixed
- **W0-C02 (tests):** `tests/integration/test_main.py` agora é hermético contra um `.env` local preenchido — `monkeypatch.delenv` cobria só o ambiente do processo, não o **arquivo** `.env`; com R2/Supabase reais configurados (validação do C01), o teste "sem R2" via R2Storage e falhava. Adicionado `monkeypatch.chdir(tmp_path)` para que o `.env` relativo não seja encontrado. Novo *fixture* autouse `_isola_logging_global` em `conftest.py` impede que a (re)configuração global de logging do keep-alive vaze entre testes.
- **W0-C01:** `alembic.ini` mantido em ASCII puro — o Alembic lê o `.ini` com o encoding do locale do SO (cp1252 no Windows) e acentos quebravam o parse.
- **W0-C01:** `migrations/env.py` com `disable_existing_loggers=False` — rodar migrations no mesmo processo (suíte/app) não silencia mais os loggers configurados.
- **W0-C01** *(revisão adversarial multi-agente — 8 achados confirmados)*:
  - `apps/web/.env.example` estava silenciosamente fora do git (o `.env*` do `.gitignore` aninhado do create-next-app o ignorava) — adicionada a negação `!.env.example` e o arquivo versionado;
  - job `web` do CI quebraria no boot: `pnpm/action-setup@v4` sem fonte de versão — adicionado `"packageManager": "pnpm@11.5.3"` em `apps/web/package.json` + `package_json_file` na action;
  - `.dockerignore` da API não cobria `__pycache__`/`.pyc` aninhados (padrões ancorados na raiz do contexto) — trocados por `**/__pycache__/` e `**/*.py[cod]`;
  - access log duplicado e sem correlação: `uvicorn.access` agora é silenciado — o access log estruturado do `RequestIdMiddleware` é a única linha por requisição;
  - envelope 500 do catch-all saía sem headers CORS (frontend cross-origin via erro de rede opaco e perdia o `request_id`) — catch-all movido para `ErrorHandlingMiddleware` interno ao CORS, com teste de regressão.

<!--
Modelo de entrada por componente:

### Added
- **W0-C01:** estrutura do monorepo (Ports & Adapters), app factory FastAPI, health check, adapter R2 (boto3), Alembic configurado, logging estruturado, CI inicial.

### Changed
- ...

### Fixed
- ...
-->

---

## Histórico de versões do produto (contexto)

> Esta seção registra a linha do tempo das **especificações** anteriores ao código. A baseline de implementação é a **v1.0**.

- **Produto v1.0 (Jun/2026)** — linha de base única e definitiva: 14 estados, 4 rotas, seleção manual e imutável da rota, laminação na clicheria com travessias do motorista, RBAC em duas camadas, identificação por câmera + digitação manual, assinatura no fluxo, responsividade mobile, animações leves e pilares de robustez/escalabilidade/mínimo de requisições/observabilidade.
- **DAT v3.0 (Abr/2026)** — documento de arquitetura técnica (stack e padrões). Usado como referência de stack; ressalvas em `CLAUDE.md §2.1`.
