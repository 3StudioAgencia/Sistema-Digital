# Prompt de Execução — W0-C01 · Configuração de Infraestrutura

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) já na raiz do repositório. Este é o **primeiro componente** do projeto e estabelece a fundação de toda a aplicação. Trabalhe a sessão inteira neste único componente, do começo ao fim.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Ele é a autoridade do projeto. Em especial, internalize:
- **§2** (hierarquia de fontes da verdade) e **§2.1** (divergências: 4 rotas, 14 estados, rota **manual e imutável** — nunca infira rota por localização).
- **§3** (pilares: robustez, escalabilidade, mínimo de requisições, animações leves, observabilidade).
- **§4** (stack) e **§5** (arquitetura Ports & Adapters + layout do monorepo).
- **§11** (o que NÃO fazer).

Decisões já registradas que regem esta sessão: **ADR-001, ADR-002, ADR-003, ADR-007, ADR-009, ADR-010** (em `DECISIONS.md`). As marcadas como *Proposta* devem ser **confirmadas ou ajustadas** ao final desta sessão, com base no que você efetivamente implementou.

---

## 1. Objetivo do componente

Estabelecer a **fundação de infraestrutura** sobre a qual todos os 19 componentes seguintes serão construídos: estrutura do monorepo em **Ports & Adapters**, esqueleto do backend FastAPI **stateless** com conexão assíncrona ao PostgreSQL (pool reaproveitado), **Alembic** configurado para migrations versionadas, adapter de **storage Cloudflare R2 (boto3)**, **logging estruturado** com `request_id`, **health checks** observáveis, esqueleto do frontend **Next.js (App Router + TypeScript strict + CSS Modules)**, **CI** e pipeline de deploy parametrizável — tudo dentro do **free tier (custo R$ 0)**.

Referências: Backlog **C01** (escopo, critérios, notas) · DAT **§1, §2** · Requisitos **RNF-011, RNF-018, RNF-024**.

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- Estrutura completa do monorepo (`apps/api`, `apps/web`, `docs/`, `.github/`, raiz).
- Backend FastAPI: app factory, configuração por ambiente, sessão/engine assíncronos do banco com a estratégia de conexão do **ADR-007**, logging estruturado, **porta de storage** + **adapter R2**, **health checks**, middleware de `request_id`, tratador de erros base, *composition root* em `main.py`.
- Alembic configurado para modo assíncrono + **migration baseline** (sem tabelas de domínio) + pasta `migrations/rls/` (vazia, com README).
- Frontend Next.js: scaffolding App Router + TS strict + CSS Modules, wiring de env, **client Supabase mínimo** (somente configuração, **sem** lógica de auth), página de status e configuração de lint/format.
- `docker-compose.yml` (Postgres local para dev/testes), `Dockerfile` da API (multi-stage), `.env.example` de ambas as apps, `.gitignore`, `.editorconfig`.
- CI (GitHub Actions): lint + tipos + testes (com Postgres de serviço, rodando `alembic upgrade head`) + build do web. Passo de deploy **documentado e parametrizável** (não precisa de credenciais reais para existir).
- Testes desta camada (ver §6).
- Atualização dos documentos de contexto (Protocolo de Encerramento, §8).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ Qualquer **tabela de domínio** (`usuarios`, `provas_digitais`, `movimentacoes`, etc.) ou enums de domínio (`rota_enum`, `status_prova_enum`). Pertencem aos componentes 04/06/09.
- ❌ **Autenticação/login**, verificação de JWT, gestão de sessão (Componente 03). Apenas **deixe o terreno pronto** (config, dependências previstas).
- ❌ **RLS** propriamente dita e a propagação de claims por request (ADR-008 / Componente 05). Crie **somente** a pasta `migrations/rls/` + README explicando a política de versionamento.
- ❌ Cron de keep-alive (Componente **02**, próxima sessão).
- ❌ Qualquer regra de negócio, UI de domínio ou máquina de estados.

> Se você sentir vontade de "adiantar" algo fora do escopo, **pare** e registre como pendência em `SESSION_LOG.md`. Componentes pequenos e bem fechados são o objetivo.

---

## 3. Restrições técnicas (obrigatórias)

1. **Stack exatamente como `CLAUDE.md §4` / DAT §1.** Para versões "≥", instale a **última estável** e **pine** (commite os lockfiles). Python alvo **3.12**.
2. **Backend stateless** desde a base (RNF-018): nenhum estado em memória de processo; pronto para escala horizontal.
3. **Estratégia de conexão (ADR-007):**
   - **Runtime da app** → pooler de transação do Supabase (porta 6543) com `asyncpg`, `statement_cache_size=0` e SQLAlchemy **`NullPool`** (pooling delegado ao PgBouncer).
   - **Alembic/migrations** → conexão **direta/sessão** (porta 5432).
   - Exponha as **duas** URLs como variáveis distintas (`DATABASE_URL` e `MIGRATIONS_DATABASE_URL`). Em dev local (Postgres do docker-compose), ambas podem apontar para a mesma instância.
4. **Segredos só em variáveis de ambiente.** Nada sensível versionado. `.env.example` documenta **todas** as chaves com descrição (sem valores reais).
5. **Observabilidade (RNF-024):** logging **estruturado em JSON** com correlação por `request_id` (gerado por requisição, propagado em logs e devolvido em header de resposta, ex.: `X-Request-ID`). Erros não tratados são capturados e logados em nível crítico, com resposta de erro padronizada (sem vazar stack trace ao cliente).
6. **Realismo de credenciais:** assuma que **Supabase e R2 reais podem não estar disponíveis** no ambiente de execução. Portanto:
   - Tudo deve **rodar e ser testável** contra o **Postgres local** (docker-compose) e um storage **mockável** (ex.: `moto` para S3, ou um adapter fake injetável).
   - O **readiness check** deve **degradar com clareza** (reportar cada dependência como `ok`/`down` sem derrubar o processo).
   - Documente em `docs/` o passo-a-passo de provisionamento real (criar projeto Supabase, criar bucket R2, preencher `.env`).
7. **Custo R$ 0:** nenhuma escolha que implique cobrança no free tier.

---

## 4. Entregáveis detalhados

> Os caminhos abaixo são o **alvo**. Use nomes idiomáticos onde o documento não for explícito, mantendo a coerência com `CLAUDE.md §5.1`. Comente o "porquê" das decisões não óbvias.

### 4.1 Raiz do repositório
- `.gitignore` (Python, Node, env, build, OS), `.editorconfig`.
- `docker-compose.yml` — serviço `db` (PostgreSQL, versão compatível com Supabase) com healthcheck, volume e porta exposta para dev/testes.
- Confirmar que os 5 documentos de contexto já existentes na raiz seguem íntegros (não sobrescreva; apenas atualize no encerramento).

### 4.2 Backend — `apps/api/`
**Configuração de projeto**
- `pyproject.toml` (gerenciado por **uv** — ADR-010): dependências de runtime (`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]>=2`, `asyncpg`, `pydantic>=2`, `pydantic-settings`, `alembic`, `boto3`, `pyjwt>=2.8`, `python-json-logger` ou equivalente) e de dev (`pytest>=8`, `pytest-asyncio>=0.23`, `pytest-cov`, `httpx`, `ruff`, `mypy`, `moto`). Configure **ruff** e **mypy (strict)** no `pyproject.toml`. Commite o lockfile.
- `.env.example` com (no mínimo): `APP_ENV`, `DATABASE_URL`, `MIGRATIONS_DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET` (previsto p/ Wave 1, documentado), `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `LOG_LEVEL`, `CORS_ALLOWED_ORIGINS`. Cada chave com comentário.
- `Dockerfile` multi-stage (build enxuto, usuário não-root, `uvicorn` como entrypoint, healthcheck).

**Código (`apps/api/src/`) — respeitando a regra de dependência hexagonal (`CLAUDE.md §5.2`)**
- `infrastructure/config.py` — `Settings` (pydantic-settings), carregado por ambiente; sem segredos default; validação na inicialização.
- `infrastructure/logging.py` — configuração de logging estruturado JSON; helper de correlação por `request_id` (ex.: `contextvars`).
- `infrastructure/database.py` — criação do **engine async** (NullPool + `statement_cache_size=0` no runtime), `async_sessionmaker`, dependência `get_session` para FastAPI, e um **`UnitOfWork`/sessão por request** desenhado de forma que a futura propagação de claims/RLS (ADR-008) caiba **sem refatoração estrutural** (deixe o ponto de extensão documentado, **mas não implemente RLS agora**).
- `application/ports/storage.py` — **`StoragePort`** (interface abstrata): `upload(key, data, content_type) -> str`, `download(key) -> bytes`, `delete(key) -> None`, `health() -> bool` (ou assinatura equivalente, bem tipada).
- `adapters/outbound/storage/r2_storage.py` — **`R2Storage`** implementando `StoragePort` via boto3 (cliente S3 apontando para o endpoint do R2). Configurável por env; sem credenciais hardcoded.
- `adapters/inbound/http/middleware.py` — middleware de `request_id` (gera/propaga, injeta header de resposta).
- `adapters/inbound/http/errors.py` — handlers de exceção: resposta de erro padronizada (JSON), log crítico para erros não tratados, **sem vazar stack trace**.
- `adapters/inbound/http/health.py` — router com:
  - **`GET /health`** (liveness): responde `200` imediatamente, sem tocar dependências.
  - **`GET /health/ready`** (readiness): verifica **banco** (`SELECT 1`) e **storage** (`StoragePort.health()`), retornando o status de cada dependência; `200` se tudo `ok`, `503` se alguma essencial estiver `down`. Estrutura clara, ex.: `{ "status": "...", "checks": { "database": "ok", "storage": "down" }, "version": "...", "env": "..." }`.
- `adapters/inbound/http/app.py` — **app factory** `create_app()`: instância FastAPI, registra middlewares (request_id, CORS via env), handlers de erro, routers (health), e expõe OpenAPI em `/docs`.
- `main.py` — **composition root**: lê `Settings`, instancia adapters concretos (R2Storage), injeta nas portas, chama `create_app()`. É o único lugar onde concreto encontra abstrato.

**Migrations (`apps/api/migrations/`)**
- Alembic configurado para **execução assíncrona** (`env.py` usando `MIGRATIONS_DATABASE_URL`, conexão direta).
- `alembic.ini` na pasta `apps/api/`.
- **Migration baseline** (`versions/0001_baseline.py`): **sem tabelas de domínio**. Pode habilitar extensão idempotente que será usada adiante: `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (provê `gen_random_uuid`). `downgrade` correspondente. O objetivo é validar que `alembic upgrade head` roda em ambiente limpo.
- `migrations/rls/README.md` — explica a política: **toda** policy RLS é um `.sql` versionado aqui **antes** de aplicar; reaplicar após recriação de tabela; uma policy por perfil × tabela sensível. (Sem `.sql` de RLS ainda.)

### 4.3 Frontend — `apps/web/`
- Scaffolding Next.js **App Router** + **TypeScript strict** (`tsconfig` com `strict: true`) + **CSS Modules**. **Sem** framework CSS externo.
- `.env.example`: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL` (com comentários).
- `src/lib/supabase/` — **client Supabase mínimo** (browser e/ou server), **somente configuração** (sem login, sem guardas). Servirá de base à Wave 1.
- `src/app/page.tsx` — página de status simples (CSS Modules) que confirma o build e exibe o ambiente; pode consultar `NEXT_PUBLIC_API_BASE_URL` para checar o health da API (opcional, com fallback amigável).
- ESLint + Prettier configurados; `pnpm build` e `pnpm lint` verdes.
- Commite o lockfile do **pnpm** (ADR-010).
- **Não** crie `middleware.ts` de RBAC, `access-matrix.ts` nem a camada de animações agora (Waves 1 e 6). Se quiser, deixe um comentário/TODO marcando o local previsto, sem código funcional.

### 4.4 CI/CD — `.github/workflows/`
- `ci.yml`:
  - **api:** instala uv, `ruff check`, `mypy`, sobe Postgres (service container), roda `alembic upgrade head` e `pytest --cov` (falha se cobertura desta camada cair abaixo do configurado).
  - **web:** instala pnpm, `pnpm lint`, `pnpm build`.
- Passo de **deploy documentado e parametrizável** (sem segredos no repo): descreva em comentários/README como conectar Vercel (web) e o host containerizado da API (ADR-009). Não exponha credenciais; use *secrets* do repositório quando o deploy real for ligado.

### 4.5 Documentação — `docs/`
- `docs/setup-infra.md` — passo-a-passo de provisionamento real: criar projeto Supabase (obter as duas connection strings 6543/5432), criar bucket R2 + chaves, preencher os `.env`, rodar migrations, subir local. Inclua a **checklist de verificação** dos critérios de aceitação (§5).

---

## 5. Critérios de aceitação (do Backlog C01 — devem ser demonstráveis)

Ao final, demonstre objetivamente cada item:

1. ✅ **`alembic upgrade head` aplica em ambiente limpo** (contra o Postgres do docker-compose), criando a baseline sem erros; `downgrade` também funciona.
2. ✅ **Upload e leitura de um arquivo de teste no storage funcionam via a porta** — comprovado por teste automatizado (com `moto`/fake) **e** com instruções para validar contra o R2 real quando houver credenciais.
3. ✅ **Health check respondendo** (RNF-024): `GET /health` retorna `200`; `GET /health/ready` reporta o status de banco e storage. Documente como acessar no staging quando o deploy estiver ligado.
4. ✅ **Variáveis sensíveis fora do código** — confirme que nenhum segredo está versionado e que `.env.example` cobre todas as chaves.
5. ✅ **Custo-alvo R$ 0** — nenhuma escolha fora do free tier.

Critérios adicionais de qualidade desta sessão:
6. ✅ `ruff`, `mypy (strict)`, `pytest` e `pnpm build/lint` **verdes** localmente e no CI.
7. ✅ Backend sobe com `uvicorn` e expõe `/docs` (OpenAPI).
8. ✅ A regra de dependência hexagonal é respeitada (o `domain` não importa nada de fora; o `main.py` é o único *composition root*).

---

## 6. Testes desta camada

Implemente, no mínimo:
- **Config:** `Settings` carrega de env e valida campos obrigatórios.
- **Health liveness:** `GET /health` → `200` sem tocar dependências.
- **Health readiness:** `GET /health/ready` com banco up + storage fake up → `200` e estrutura de checks correta; simule storage `down` → `503` e `checks.storage == "down"`.
- **Storage port:** `upload` seguido de `download` retorna o mesmo conteúdo (via `moto` ou adapter fake injetado).
- **DB connectivity:** sessão async executa `SELECT 1` com sucesso contra o Postgres de teste.
- **Request-ID:** resposta inclui o header de correlação; o mesmo id aparece no log da requisição.

Use `pytest-asyncio` e `httpx.AsyncClient`. Garanta que a suíte roda **offline** (sem Supabase/R2 reais).

---

## 7. Ordem de execução sugerida

1. Leia `CLAUDE.md` e confirme a hierarquia de fontes (§2).
2. Scaffolding do monorepo + raiz (.gitignore, .editorconfig, docker-compose).
3. Backend: config → logging → database → portas → adapter R2 → middlewares/errors → health → app factory → main. Comente decisões não óbvias.
4. Alembic + baseline + `migrations/rls/README.md`. Rode `alembic upgrade head` no Postgres local.
5. Testes do backend; rode tudo verde.
6. Frontend: scaffolding + env + client Supabase mínimo + página de status; `pnpm build/lint` verdes.
7. CI (`ci.yml`) e `docs/setup-infra.md`.
8. Verifique **todos** os critérios de aceitação (§5) e a sub-checklist da DoD (§8).
9. Execute o **Protocolo de Encerramento** (§8).

> Vá em incrementos pequenos e verificáveis; rode os testes com frequência. Se uma decisão de arquitetura surgir no caminho (ex.: detalhe do pooler, formato do log), **decida com base nos pilares**, implemente e **registre o ADR** no encerramento.

---

## 8. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`, descreva o que o W0-C01 entregou.
2. **`DECISIONS.md`** — **confirme ou ajuste** ADR-003, ADR-007, ADR-010 com base no que foi de fato implementado (mude o status de *Proposta* para *Aceita* quando aplicável) e registre **qualquer** nova decisão tomada na sessão.
3. **`SESSION_LOG.md`** — nova entrada (use o modelo do topo do arquivo): objetivo, feito, decisões, testes/cobertura, **pendências** e **próximo passo** (= **W0-C02 · Cron de Keep-Alive**).
4. **`CLAUDE.md`** — atualize **§9 (comandos)** com os comandos reais que passaram a funcionar; ajuste o que mais tiver mudado estruturalmente. Mantenha enxuto e verdadeiro.
5. **`README.md`** — atualize setup/comandos e marque o status da Wave 0 no roadmap.
6. Verifique a **Definition of Done** aplicável a este componente (subconjunto do `CLAUDE.md §8`: testes, migrations versionadas, sem erros de console/log crítico, docs do módulo, observabilidade, error handling). Marque o status no roadmap do README.
7. **Commits semânticos** (`feat(w0-c01): ...`, `chore(w0-c01): ...`), árvore limpa, **sem segredos versionados**, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, evidência de cada critério de aceitação (§5), pendências em aberto e o comando exato para iniciar a próxima sessão (W0-C02).

---

### Lembrete final
Robustez, escalabilidade, mínimo de requisições, animações leves e observabilidade não são opcionais — são os pilares que tornam este sistema profissional. Esta fundação precisa ser **sólida o bastante para os outros 19 componentes se apoiarem nela sem retrabalho.** Faça a melhor engenharia possível.
