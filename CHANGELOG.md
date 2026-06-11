# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

> **Convenção:** registre as mudanças em `[Unreleased]`, agrupadas por categoria (*Added, Changed, Deprecated, Removed, Fixed, Security*), referenciando o componente (ex.: `W0-C01`). Ao concluir uma wave ou liberar uma versão, mova o bloco para uma seção versionada com data.

---

## [Unreleased]

### Security
- **W1-C03:** mensagens de autenticação **genéricas** (o login e o `GET /auth/me` 401 não revelam qual checagem falhou — anti-enumeração, CLAUDE.md §11); sessão em **cookies HTTP-only** (`@supabase/ssr`); respostas de refresh com `Cache-Control: no-store` (não-cacheáveis por CDN/ISR — evitam servir a sessão de um usuário a outro); o PNG-fonte de 17,8 MB do herói fica **fora do git e do bundle** (`.gitignore`), servindo-se só o `login-bg.jpg` otimizado.
- **Remediação W0 (W0-REMEDIATION):** `Settings` rejeita origem curinga (`*`) no CORS enquanto `allow_credentials` está ativo — bloqueia reflexão de origem com credenciais (**W0-A-015**); `X-Content-Type-Options: nosniff` + `Cache-Control: no-store` em **toda** resposta (**W0-A-016**); `X-Request-ID` recebido passa por whitelist `^[A-Za-z0-9._-]{1,128}$`, caindo para `uuid4` fora do padrão (**W0-A-023**); actions de terceiros **pinadas por SHA** + `.github/dependabot.yml` (github-actions/pip/npm) (**W0-A-008**); keep-alive não vaza a connection string nem na falha de carga de config (`hide_input_in_errors` + `get_settings()` dentro do contrato de erro do `main()`) (**W0-A-005**).

### Changed
- **W1-C03 (web, refino de motion):** contorno dos inputs com **fade-in/out no foco** (overlay só de `opacity` — GPU, no lugar da borda instantânea) e **animações harmonizadas** — todas as interações (hover/press de botões e do herói + parallax) usam uma **mola única** (`SPRING` em `lib/motion/tokens.ts`), com *stagger* (0.07/0.06) e easing consistentes (DAT §5.1: entrada `emphasized`, saída `exit`, fade `standard`). Emenda à ADR-020.
- **W1-C03 (web, refino):** fluxo de login virou **rota única adaptativa** (`/login`): no **mobile, as boas-vindas aparecem PRIMEIRO** e o formulário é revelado ao clicar em "Entrar" (troca de passo, sem redirect por viewport — corrige o login aparecendo antes no mobile); `/` e `/bem-vindo` redirecionam para `/login`; adicionado `export const viewport`. Herói do **desktop com o formato custom EXATO do Figma** (máscara SVG `login-shape.svg`, não mais `border-radius`). Animações mais imersivas: **parallax do herói no hover**, microinterações de foco dos campos e hover/press dos botões, transição boas-vindas→formulário (`AnimatePresence`) — tudo `transform`/`opacity` e reduced-motion-aware. ADR-022.
- **W1-C03 (web):** convenção do App Router migrada de `middleware.ts` → **`src/proxy.ts`** (Next 16 deprecou `middleware`; ADR-021); **Inter self-hospedada via `next/font/local`** substitui a fonte de sistema para a UI do produto, mantendo o build hermético (emenda à ADR-014).
- **Remediação W0:** R2 com `connect_timeout`/`read_timeout=5s` + `max_attempts=1`, alinhados ao orçamento de 5s do readiness (**W0-A-004**); CI dispara também em `push` para `develop` (**W0-A-002**); workflows endurecidos — `permissions: contents: read` e `concurrency` no `ci.yml`, `pnpm format:check` no job web, keep-alive com `uv sync/run --no-dev` (**W0-A-009/010/011/024**); `Dockerfile` sem `--chown` (código/venv não graváveis pelo usuário de runtime) (**W0-A-029**); `coerce_asyncpg_url` tornado público (**W0-A-022**).

### Fixed
- **Remediação W0 (W0-REMEDIATION):** corrigidos os 29 achados da auditoria (`docs/audits/wave-0-audit.md`); log de correções, evidências e gate em `docs/audits/wave-0-remediation.md`. Destaques de robustez/observabilidade: `ping`/`R2Storage.health`/checks do readiness logam `WARNING` com `error_type` ao degradar para `down`, fechando o gap de diagnóstico (**W0-A-003**); `LOG_LEVEL` validado no boot, citando a variável (**W0-A-013**); suíte hermética contra variáveis de shell, não só o `.env` (**W0-A-012**); downgrade da baseline não dropa a extensão compartilhada `pgcrypto` em staging/produção (**W0-A-014**); página de status valida `response.ok/503` e o shape do corpo, com `error.tsx` cobrindo a rota (**W0-A-017**). Docs/ADRs: emenda da ADR-013 + docstrings de `errors.py` (**W0-A-007**), `keep-alive.md §6` (branch padrão) (**W0-A-006**), `.env.example` (APP_ENV/IPv6) (**W0-A-020/021**), `CLAUDE.md §5.1` (`tasks/`) (**W0-A-019**), README (ADR-010) (**W0-A-028**), **ADR-017** (lar das implementações de porta de DB) (**W0-A-018**); nits de teste/convenção (**W0-A-025/026/027**).
- _Pendente do responsável (não-código):_ cadastrar o secret `KEEPALIVE_DATABASE_URL` no GitHub para ligar o keep-alive (**W0-A-001**).

### Added
- **W1-C03 (api):** autenticação por e-mail/senha com **verificação de JWT** do Supabase no backend (`adapters/inbound/http/auth.py`): `JwtVerifier` robusto a **ES256 via JWKS (cacheado, `PyJWKClient`) + HS256 fallback**, validando `aud="authenticated"` e `exp`; endpoint de prova **`GET /auth/me`** (identidade verificada, sem ida ao banco); erros → **401 genérico** com `WWW-Authenticate: Bearer`, logando só o `error_type`. `Settings` ganhou `SUPABASE_JWKS_URL` (derivado de `SUPABASE_URL`) + `effective_jwks_url`; dependência `pyjwt[crypto]` (cryptography) para ES256. 18 testes offline (ES256 com JWKS dublê, HS256, expirado, `aud` errada, assinatura inválida, `alg=none`, `sub` não-string, deny-all). Cobertura do backend **98%**.
- **W1-C03 (web):** login via **`@supabase/ssr`** — clients de **browser** e **servidor** + helper `updateSession` e **`src/proxy.ts`** (Next 16; **só refresh** de sessão, proteção via `getUser()`), com `Cache-Control: no-store` no refresh. **Três telas** fiéis ao Figma em CSS Modules (`/login` adaptativa desktop-split/mobile · `/bem-vindo` boas-vindas mobile · `/inicio` landing placeholder com prova `AuthProof → /auth/me` + botão Sair), **erro de login genérico** e **encerramento por inatividade de 30 min** (`InactivityGuard` → `signOut` + `/login?expirado=1`). Fundação mínima de **motion** (`lib/motion/tokens.ts` = DAT §5.1; `useReducedMotion`) com animações **Framer Motion** sobre os tokens (só transform/opacity, reduced-motion-aware). **Inter** self-hospedada (`next/font/local`); imagem-herói otimizada (**17,8 MB → 540 KB**).
- **W1-C03 (web/tests):** infra de teste do frontend — **vitest + React Testing Library** (11 testes: render das telas, login OK → `/inicio`, erro genérico, inatividade com *fake timers*, reduced-motion) e **Playwright** E2E (split desktop, boas-vindas → login, *touch targets* ≥ 44px, credenciais inválidas → erro genérico; caminho feliz autenticado atrás de `E2E_LIVE`).
- **W1-C03 (docs):** `docs/auth.md` (arquitetura de login/sessão, verificação ES256/JWKS+HS256, regra dos 30 min, cuidado de cache de CDN, validação local e checklist de aceitação). **ADR-018 a ADR-021** + emenda da ADR-014 em `DECISIONS.md`.
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
