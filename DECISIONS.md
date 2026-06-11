# DECISIONS.md — Architecture Decision Records (ADRs)

> Registro leve e cronológico das decisões de arquitetura do projeto. Formato por ADR: **Contexto → Decisão → Status → Consequências**.
> **Status possíveis:** `Aceita` · `Proposta` (a confirmar em uma wave específica) · `Substituída por ADR-XXX` · `Revisável`.
> Toda decisão tomada em sessão deve virar (ou atualizar) um ADR aqui — conforme o Protocolo de Encerramento (CLAUDE.md §10).

---

## ADR-001 — Monorepo único (`apps/api` + `apps/web`)
- **Contexto:** Frontend e backend evoluem juntos e compartilham invariantes críticas (ex.: Matriz de Acesso espelhada em `access-matrix.ts` ↔ RLS exige PR único cobrindo as duas camadas).
- **Decisão:** Monorepo com `apps/api` (FastAPI) e `apps/web` (Next.js), docs e CI na raiz.
- **Status:** Aceita.
- **Consequências:** Um único histórico/PR garante sincronia entre camadas. Sem ferramenta pesada de monorepo (Nx/Turborepo) na v1.0 — pode ser reavaliado se a orquestração crescer (ADR-010).

## ADR-002 — Arquitetura Hexagonal (Ports & Adapters) no backend
- **Contexto:** Backlog C01 e DAT exigem estrutura que permita adicionar rotas/estados/regras sem refatoração estrutural (RNF-012) e isolar o domínio do framework/infra.
- **Decisão:** `domain` (puro) → `application` (casos de uso + portas) → `adapters` (inbound HTTP, outbound DB/storage/auth) → `infrastructure`/`main` (wiring). Dependências apontam para dentro.
- **Status:** Aceita.
- **Consequências:** Domínio testável sem I/O; troca de adapter (ex.: storage) sem tocar no núcleo; mais boilerplate inicial, compensado pela testabilidade e longevidade.

## ADR-003 — Stack conforme DAT v3.0 §1, com pinagem da versão instalada
- **Contexto:** A stack está fixada no DAT; algumas versões dizem "≥" (Next ≥14, Python ≥3.11).
- **Decisão:** Adotar a stack do DAT. Para itens "≥", instalar a **última estável** no momento da execução e **pinar a versão exata** (lockfiles versionados). Python alvo **3.12** (piso 3.11). Next.js: última estável do App Router.
- **Status:** Aceita — executada no W0-C01. Versões pinadas na fundação: Python 3.12.13 · FastAPI 0.136.3 · SQLAlchemy 2.0.50 · Pydantic 2.13.4 · Alembic 1.18.4 · asyncpg 0.31.0 · boto3 1.43.26 · PyJWT 2.13.0 · pytest 9.0.3 · Next 16.2.9 · React 19.2.4 · TypeScript 5.x (lockfiles = fonte exata).
- **Consequências:** Builds reproduzíveis. Atualizações de versão maior viram ADR próprio.

## ADR-004 — Rota manual e imutável, com 4 rotas (sobrepõe UML/DAT v3.0)
- **Contexto:** O UML v3.0 e trechos do DAT modelam rota **inferida pela localização** (2 rotas, coluna nullable "set on approval"). Os **Requisitos v1.0 (RN-007)** determinam o oposto.
- **Decisão:** A rota é **escolhida manualmente pelo Administrador na criação**, entre `matriz | lam_matriz | filial | lam_filial`, **independe** da localização do vendedor e é **imutável** após criar. Coluna `rota` **`NOT NULL`** desde a primeira migration; imutabilidade reforçada no domínio (Pydantic) **e** por constraint no banco. Localização do vendedor é **apenas informativa**.
- **Status:** Aceita. **Prevalece sobre o UML/DAT v3.0.**
- **Consequências:** Erro de escolha só se corrige por cancelar + recriar (mitigado por dupla confirmação na tela de criação — Backlog §6 Riscos). UML deve ser regenerado (ADR-011).

## ADR-005 — Máquina de estados em código, não no banco (14 estados)
- **Contexto:** DAT §4 e Backlog C11. Criticidade altíssima do componente.
- **Decisão:** `TRANSITION_RULES` imutável em `apps/api/src/domain/state_machine/rules.py`, indexada por `(rota, estado_atual)`. Sem wildcard. Cobertura **≥ 95%**. Enums Python sincronizados com PostgreSQL via fluxo do DAT §4.5 (PR bloqueado se tocar só um lado).
- **Status:** Aceita.
- **Consequências:** Revisão por code review > mudança de dado em produção; rollback = revert de commit; regras servem como documentação executável.

## ADR-006 — RBAC defesa em profundidade (middleware + RLS)
- **Contexto:** Requisitos §7 (fonte única), RN-013, RNF-007.
- **Decisão:** Camada superior = middleware App Router + `lib/access-matrix.ts`; camada inferior = RLS versionada em `migrations/rls/`. Negação em qualquer camada basta. Toda alteração da Matriz = **PR único** nas duas camadas, com teste de equivalência.
- **Status:** Aceita (implementação plena em Wave 1 / C05).
- **Consequências:** Defesa redundante; custo de manter dois artefatos sincronizados, controlado por checklist de PR e testes automatizados.

## ADR-007 — Estratégia de conexão ao Supabase Postgres
- **Contexto:** Backend stateless e horizontalmente escalável (RNF-018) sobre Postgres gerenciado do Supabase, que oferece conexão **direta (5432)** e **pooler de transação via PgBouncer (6543)**. Em modo transação, prepared statements/recursos de sessão não são suportados.
- **Decisão:** Runtime da aplicação usa o **pooler de transação (6543)** com `asyncpg` + SQLAlchemy `NullPool` (pooling delegado ao PgBouncer) e **ambos** os caches de prepared statement desligados: `statement_cache_size=0` (cache do asyncpg) **e** `prepared_statement_cache_size=0` (cache do dialeto asyncpg do SQLAlchemy) via `connect_args` → seguro para escala horizontal. **Migrations (Alembic)** usam a **conexão direta/sessão (5432)**, pois DDL exige recursos de sessão (`migrations/env.py` lê `MIGRATIONS_DATABASE_URL` e não exige o `Settings` completo).
- **Status:** **Aceita** — implementada e validada no W0-C01 (`src/infrastructure/database.py`); suíte de integração executada contra PostgreSQL 17.10 real (66 testes, ciclo completo do Alembic). **Validada também contra o Supabase real em 2026-06-10** (runtime 6543 + migrations + readiness 200).
- **Emenda (2026-06-10):** a conexão direta (`db.<ref>.supabase.co:5432`) é **somente IPv6** em projetos novos do Supabase. Em redes sem IPv6, `MIGRATIONS_DATABASE_URL` usa o **pooler em modo session** (porta 5432, usuário `postgres.<ref>`), que é 1:1 e suporta DDL — validado com `alembic upgrade head` aplicado no projeto real por essa via. Em hosts com IPv6, a conexão direta permanece a preferência.
- **Consequências:** Duas URLs de conexão (`DATABASE_URL` runtime vs `MIGRATIONS_DATABASE_URL`), documentadas em `.env.example`. Em dev local ambas apontam para o Postgres do docker-compose.

## ADR-008 — Como o backend honra a RLS por requisição
- **Contexto:** Os exemplos de RLS do DAT §7.2 usam `auth.jwt()`. Conexões com a *service role* **ignoram** RLS por padrão. Um backend próprio precisa propagar os claims do usuário ao Postgres para que `auth.jwt()`/escopo funcionem como camada inferior real.
- **Decisão (proposta):** Por requisição autenticada, o backend define os claims na sessão do banco com `SET LOCAL request.jwt.claims = '<json>'` (e papel `authenticated`) dentro da transação, de modo que as policies baseadas em `auth.jwt()` resolvam corretamente; **nunca** operar o fluxo do usuário com credenciais que façam *bypass* de RLS.
- **Status:** **Proposta** — desenhar/validar na Wave 1 / C05. Apenas registrada agora para não ser esquecida.
- **Consequências:** Define o padrão de Unit of Work/sessão por request. Impacta o adapter de banco (a ser previsto, sem implementar a lógica de RLS, na C01).

## ADR-009 — Alvos de deploy (revisável)
- **Contexto:** Backlog C01 exige pipeline de deploy (web + api) e staging acessível com health check, dentro do free tier. Plataformas não foram especificadas pelo cliente.
- **Decisão (proposta/revisável):** **Web (Next.js)** → Vercel (free; melhor suporte a App Router + middleware). **API (FastAPI)** → **containerizada (Dockerfile)** e portável; alvo de referência free tier a confirmar (ex.: Fly.io ou Render). CI agnóstica de plataforma (GitHub Actions: lint, types, testes com Postgres de serviço, build, `alembic upgrade head` no staging).
- **Status:** **Proposta / Revisável** — confirmar plataformas com o responsável antes do deploy real. O **core portável** (Docker + CI) não muda com a escolha.
- **Consequências:** Trocar de host afeta só o passo de deploy. Documentar o procedimento escolhido no README quando confirmado.

## ADR-010 — Gerenciadores de pacote: `uv` (Python) e `pnpm` (web)
- **Contexto:** Pedido de stack moderna e builds rápidos/reproduzíveis.
- **Decisão:** **`uv`** para o backend (resolução rápida, `pyproject.toml`, `uv.lock`) e **`pnpm`** para o frontend (`pnpm-lock.yaml`). Sem orquestrador de monorepo na v1.0. Build scripts do pnpm 11 aprovados explicitamente em `pnpm-workspace.yaml` (`sharp`, `unrs-resolver`) — bloqueio por padrão é proteção de supply chain.
- **Status:** **Aceita** — confirmada no W0-C01 (uv 0.11 / pnpm 11 no ambiente alvo; lockfiles versionados; CI usa `uv sync --frozen` e `pnpm install --frozen-lockfile`).
- **Consequências:** Lockfiles versionados; comandos padronizados no README e CLAUDE.md §9.

## ADR-011 — Tratamento dos documentos desatualizados (UML/DAT v3.0)
- **Contexto:** UML v3.0 desatualizado (2 rotas / ~10 estados / rota inferida); DAT v3.0 tem referências cruzadas a "Requisitos v4.0" e uma estratégia de migração (DAT §6) inaplicável a greenfield.
- **Decisão:** **Requisitos v1.0 + Backlog v1.0 = fonte única** de negócio/escopo. DAT v3.0 vale **apenas** para stack/padrões, com as ressalvas de CLAUDE.md §2.1. **DAT §6 (migração) é IGNORADO.** O **UML será regenerado** (4 rotas, 14 estados, rota manual/imutável) como tarefa de documentação após a Wave 2.
- **Status:** Aceita.
- **Consequências:** Evita que o Claude Code reintroduza o modelo antigo. Divergências novas devem ser registradas como ADR aqui.

## ADR-012 — Porta de storage SÍNCRONA, executada via threadpool (W0-C01)
- **Contexto:** O SDK concreto do R2 (boto3) é síncrono; a API é async. Uma porta async exigiria wrapper assíncrono artificial sobre boto3 ou troca de SDK (aioboto3, menos maduro).
- **Decisão:** `StoragePort` tem assinatura **síncrona** (`upload/download/delete/health`); os handlers async chamam a porta via `run_in_threadpool` (caso do readiness). A porta não conhece boto3 — o cliente S3 é **injetado** no `R2Storage`, o que permite testar com `moto` sem rede nem env.
- **Status:** Aceita (W0-C01).
- **Consequências:** Event loop nunca bloqueia; trocar boto3 por SDK async no futuro = novo adapter, sem tocar a porta. `UnconfiguredStorage` cobre ambiente sem credenciais (readiness reporta `storage: down` sem derrubar o boot).

## ADR-013 — Catch-all de exceções DENTRO do middleware de request-id (W0-C01)
- **Contexto:** O handler genérico de `Exception` do Starlette roda no `ServerErrorMiddleware`, FORA do escopo do `ContextVar` de request_id — o log CRITICAL do erro não tratado sairia sem correlação (e o Starlette re-levanta a exceção após responder).
- **Decisão:** O `RequestIdMiddleware` captura `Exception` em volta do `call_next` e delega a `log_and_build_internal_error_response()` (em `errors.py`): log CRITICAL **correlacionado** + envelope JSON 500 padronizado, sem stack trace ao cliente. O handler genérico permanece registrado como rede de segurança de última instância. Envelope canônico de erro: `{"error": {"code", "message", "request_id"}}`.
- **Status:** Aceita (W0-C01).
- **Consequências:** Toda resposta (inclusive 500) carrega `X-Request-ID`; access log uniforme. Handlers de `HTTPException`/`RequestValidationError` usam o mesmo envelope.

## ADR-014 — Fundação do frontend: Next 16 pinado, build hermético (W0-C01)
- **Contexto:** ADR-003 manda pinar a última estável. Next 16.2.9 / React 19.2.4 eram as estáveis na execução. `next/font/google` baixa fontes em build (rede) e quebraria builds herméticos/offline.
- **Decisão:** Next **16.2.9** + React **19.2.4** pinados no lockfile; **fonte de sistema** via tokens CSS (sem `next/font/google`); `turbopack.root` explícito (evita inferência errada de raiz por lockfiles fora do repo); ESLint flat config + `eslint-config-prettier` + Prettier; client Supabase **lazy** (build não exige env; runtime sim).
- **Status:** Aceita (W0-C01).
- **Consequências:** Build reproduzível sem rede além do registry; tipografia padronizada por CSS vars (a identidade visual definitiva pode revisitar na Wave 6).

## ADR-015 — Keep-alive externo do Postgres do Supabase (W0-C02)
- **Contexto:** o free tier do Supabase **pausa o projeto após 7 dias sem requisições**, o que derrubaria o banco inteiro (RNF-011). `pg_cron` pausaria **junto** com o projeto (não consegue se auto-acordar) e um scheduler embutido na API **hibernaria junto** com o host free tier — ambos inúteis para este fim.
- **Decisão:** o keep-alive é um **scheduler EXTERNO e independente do host da API** que invoca uma **rotina read-only de _ping_** ao banco. A lógica de ida ao banco é a **mesma** do readiness do C01 — `fetch_db_time()` em `src/infrastructure/database.py`, consolidada num único lugar e reutilizada por `ping()` (readiness) **e** pelo keep-alive (DRY, sem duplicação). A rotina (`src/tasks/keep_alive.py`, executável por `uv run python -m src.tasks.keep_alive`) usa a **conexão direta/sessão (5432, `MIGRATIONS_DATABASE_URL`)** para o `SELECT now()` *one-shot*, emite **um log JSON estruturado** (`event="keep_alive"`, `status`, `latency_ms`, `db_time`, `correlation_id`, `env`) e devolve **exit 0/≠0**. Em falha, registra **apenas o tipo da exceção** (`error_type`) — nunca `str(exc)` — para **não vazar a connection string** no log. **Scheduler primário:** GitHub Actions scheduled workflow (`.github/workflows/keep-alive.yml`), cadência **diária `0 9 * * *` UTC** (= 06:00 America/Sao_Paulo; Brasil sem DST desde 2019 → BRT = UTC−3 o ano todo), ~**7× de margem** sobre o limite de 7 dias e **sem polling excessivo** (RNF-023). **Alerta** (RNF-024): exit ≠ 0 → workflow vermelho → **notificação nativa do GitHub**; passo de webhook **opcional**, acionado só com `if: failure()` e se o secret existir (sem URLs/tokens hardcoded).
- **Nota de numeração:** o prompt do W0-C02 referenciava este ADR como "ADR-012", mas **012–014 já foram consumidos no W0-C01**. Adotado o próximo número livre (**015**); divergência registrada conforme `CLAUDE.md §2.1`.
- **Status:** **Aceita** (W0-C02) — validada em execução: *ping* read-only ao **Supabase real** (`exit 0`, `status="ok"`, `db_time` real, `latency_ms` medida) e falha controlada com credencial inválida (`exit 1`, `status="error"`, `error_type` sem vazar a senha).
- **Consequências:** ligar em produção = cadastrar o secret `KEEPALIVE_DATABASE_URL` (mesma string de `MIGRATIONS_DATABASE_URL`) e, opcional, `ALERT_WEBHOOK_URL`. O workflow mapeia esse único secret para `DATABASE_URL` **e** `MIGRATIONS_DATABASE_URL` (o `Settings` do C01 exige ambas no boot; a rotina usa só a direta). **Caveat:** o GitHub desabilita workflows agendados após **60 dias de inatividade do repositório** e pode atrasar/saltar execuções — a margem diária absorve atrasos; o **hardening de longo prazo é um Cloudflare Worker Cron** (mesmo ecossistema do R2, sem o limite de 60 dias), **apenas documentado** (`docs/keep-alive.md`), pois o ADR mantém o scheduler **trocável**.

---

### Próximas decisões a confirmar (checklist vivo)
- [x] ADR-007 — validado: pooler/NullPool + caches off, suíte contra PostgreSQL 17.10 real (W0/C01).
- [ ] ADR-008 — desenhar propagação de claims/RLS por request (W1/C05). Ponto de extensão pronto em `SqlAlchemyUnitOfWork.begin()`.
- [ ] ADR-009 — confirmar plataformas de deploy com o responsável (CI/Dockerfile prontos e agnósticos).
- [x] ADR-010 — confirmado: `uv` 0.11 + `pnpm` 11 no ambiente alvo (W0/C01).
