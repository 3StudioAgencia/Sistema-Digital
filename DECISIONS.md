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
- **Status:** **Aceita (plataformas) / Revisável (futuro)** — o responsável confirmou no W1-C03: **Web → Vercel**, **API → Railway** (free tier). O futuro **on-prem** (rede interna) permanece revisável. O **core portável** (Docker + CI) não muda com a escolha.
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
- **Decisão:** O catch-all delega a `log_and_build_internal_error_response()` (em `errors.py`): log CRITICAL **correlacionado** + envelope JSON 500 padronizado, sem stack trace ao cliente. Envelope canônico de erro: `{"error": {"code", "message", "request_id"}}`.
- **Status:** Aceita (W0-C01) — **emendada** (ver abaixo).
- **Emenda (revisão adversarial W0-C01, formalizada na remediação — W0-A-007):** o catch-all **principal** passou a ser um `ErrorHandlingMiddleware` dedicado, posicionado **interno ao `CORSMiddleware`**, para que o envelope 500 saia **com** os headers CORS (sem eles, um frontend cross-origin veria erro de rede opaco e perderia o `request_id`). O `RequestIdMiddleware` (mais externo, que popula o `ContextVar`) e o handler genérico do Starlette permanecem como **redes de segurança** — todos delegam à mesma função. Ordem dos middlewares, de dentro para fora: **ErrorHandling → CORS → RequestId** (ver `apps/api/src/adapters/inbound/http/app.py`). Esta emenda só corrige a documentação (a arquitetura em três camadas já estava no código desde o W0-C01).
- **Consequências:** Toda resposta (inclusive 500) carrega `X-Request-ID`; access log uniforme. Handlers de `HTTPException`/`RequestValidationError` usam o mesmo envelope.

## ADR-014 — Fundação do frontend: Next 16 pinado, build hermético (W0-C01)
- **Contexto:** ADR-003 manda pinar a última estável. Next 16.2.9 / React 19.2.4 eram as estáveis na execução. `next/font/google` baixa fontes em build (rede) e quebraria builds herméticos/offline.
- **Decisão:** Next **16.2.9** + React **19.2.4** pinados no lockfile; **fonte de sistema** via tokens CSS (sem `next/font/google`); `turbopack.root` explícito (evita inferência errada de raiz por lockfiles fora do repo); ESLint flat config + `eslint-config-prettier` + Prettier; client Supabase **lazy** (build não exige env; runtime sim).
- **Status:** Aceita (W0-C01) — **emendada no W1-C03** (ver abaixo).
- **Emenda (W1-C03):** a UI do produto passou a usar **Inter self-hospedada via `next/font/local`** (pesos 300/400/600, woff2 em `apps/web/src/app/fonts/`), substituindo a fonte de sistema **sem** quebrar o build hermético — `next/font/local` não baixa nada em build (ao contrário de `next/font/google`, que segue **proibido**). A imagem-herói do login é servida otimizada (`login-bg.jpg`, ~540 KB); o PNG-fonte (17,8 MB) fica fora do git/bundle (`.gitignore`).
- **Consequências:** Build reproduzível sem rede além do registry; tipografia padronizada por CSS vars (a identidade visual definitiva pode revisitar na Wave 6).

## ADR-015 — Keep-alive externo do Postgres do Supabase (W0-C02)
- **Contexto:** o free tier do Supabase **pausa o projeto após 7 dias sem requisições**, o que derrubaria o banco inteiro (RNF-011). `pg_cron` pausaria **junto** com o projeto (não consegue se auto-acordar) e um scheduler embutido na API **hibernaria junto** com o host free tier — ambos inúteis para este fim.
- **Decisão:** o keep-alive é um **scheduler EXTERNO e independente do host da API** que invoca uma **rotina read-only de _ping_** ao banco. A lógica de ida ao banco é a **mesma** do readiness do C01 — `fetch_db_time()` em `src/infrastructure/database.py`, consolidada num único lugar e reutilizada por `ping()` (readiness) **e** pelo keep-alive (DRY, sem duplicação). A rotina (`src/tasks/keep_alive.py`, executável por `uv run python -m src.tasks.keep_alive`) usa a **conexão direta/sessão (5432, `MIGRATIONS_DATABASE_URL`)** para o `SELECT now()` *one-shot*, emite **um log JSON estruturado** (`event="keep_alive"`, `status`, `latency_ms`, `db_time`, `correlation_id`, `env`) e devolve **exit 0/≠0**. Em falha, registra **apenas o tipo da exceção** (`error_type`) — nunca `str(exc)` — para **não vazar a connection string** no log. **Scheduler primário:** GitHub Actions scheduled workflow (`.github/workflows/keep-alive.yml`), cadência **diária `0 9 * * *` UTC** (= 06:00 America/Sao_Paulo; Brasil sem DST desde 2019 → BRT = UTC−3 o ano todo), ~**7× de margem** sobre o limite de 7 dias e **sem polling excessivo** (RNF-023). **Alerta** (RNF-024): exit ≠ 0 → workflow vermelho → **notificação nativa do GitHub**; passo de webhook **opcional**, acionado só com `if: failure()` e se o secret existir (sem URLs/tokens hardcoded).
- **Nota de numeração:** o prompt do W0-C02 referenciava este ADR como "ADR-012", mas **012–014 já foram consumidos no W0-C01**. Adotado o próximo número livre (**015**); divergência registrada conforme `CLAUDE.md §2.1`.
- **Status:** **Aceita** (W0-C02) — validada em execução: *ping* read-only ao **Supabase real** (`exit 0`, `status="ok"`, `db_time` real, `latency_ms` medida) e falha controlada com credencial inválida (`exit 1`, `status="error"`, `error_type` sem vazar a senha).
- **Consequências:** ligar em produção = cadastrar o secret `KEEPALIVE_DATABASE_URL` (mesma string de `MIGRATIONS_DATABASE_URL`) e, opcional, `ALERT_WEBHOOK_URL`. O workflow mapeia esse único secret para `DATABASE_URL` **e** `MIGRATIONS_DATABASE_URL` (o `Settings` do C01 exige ambas no boot; a rotina usa só a direta). **Caveat:** o GitHub desabilita workflows agendados após **60 dias de inatividade do repositório** e pode atrasar/saltar execuções — a margem diária absorve atrasos; o **hardening de longo prazo é um Cloudflare Worker Cron** (mesmo ecossistema do R2, sem o limite de 60 dias), **apenas documentado** (`docs/keep-alive.md`), pois o ADR mantém o scheduler **trocável**.

## ADR-016 — Modelo de branches e publicação no GitHub (gitflow leve)
- **Contexto:** ao fim do W0-C02 o repositório foi publicado no GitHub (`3studioagn/Sistema-Digital`). Era preciso um modelo de branches simples que separe linha estável de integração e conviva com a CI e com o cron do keep-alive (que roda a partir da **branch padrão**).
- **Decisão:** **gitflow leve** — `main` = linha **estável**; `develop` = **integração** (branch **padrão** no GitHub, onde os componentes seguem). Commits em Conventional Commits com escopo por componente; quando houver fluxo de PR, os PRs apontam para `develop`. Push via **HTTPS + Git Credential Manager** (o ambiente de dev **não tem `gh`**; operações de repositório pelo Git/UI do GitHub).
- **Status:** **Aceita** (W0-C02) — `main` e `develop` enviadas em `abc293c`.
- **Consequências:** (1) a CI (`.github/workflows/ci.yml`) hoje dispara em `push` para `main` **e** em `pull_request` — pushes diretos em `develop` **NÃO** acionam a CI; decidir se `develop` entra nos gatilhos de push ou se o fluxo será sempre por PR. (2) O **workflow agendado do keep-alive roda a partir da branch padrão (`develop`)** — exige o secret `KEEPALIVE_DATABASE_URL` configurado, senão a execução diária falha (ADR-015). (3) O nome do repo no GitHub (`Sistema-Digital`) **difere** do slug canônico interno (`rastreio-provas-digitais`, CLAUDE.md §1).
- **Resolução da consequência (1) (remediação W0 — W0-A-002):** `develop` foi adicionado aos gatilhos de `push` do `ci.yml` (`branches: [main, develop]`) — todo push na branch de integração passa pela CI. Mantém-se livre adotar também branch protection + PR no futuro.

## ADR-017 — Lar das implementações de porta de DB: `adapters/outbound/db/` (remediação W0)
- **Contexto:** O `SqlAlchemyUnitOfWork` (implementação da porta `application/ports/unit_of_work.py`) nasceu em `infrastructure/database.py` por instrução do prompt W0-C01. Isso criou **dois lares** para implementações de porta: o `StoragePort` é implementado em `adapters/outbound/storage/`, mas a porta de DB ficou em `infrastructure/`. A ambiguidade se materializaria na Wave 2, quando os repositórios SQLAlchemy concretos precisarem de um lar (W0-A-018).
- **Decisão:** As **implementações de porta** de banco — `SqlAlchemyUnitOfWork` e os futuros repositórios concretos — passam a viver em **`apps/api/src/adapters/outbound/db/`**, espelhando `adapters/outbound/storage/`. O `infrastructure/database.py` mantém apenas a **infra de conexão** (factories de engine/sessão, `fetch_db_time`, `ping`) — wiring, não adapter. A direção de dependência já está correta (infra/adapter → `application.ports`, para dentro); muda só a colocação.
- **Status:** **Aceita** — resolvida **documentalmente** na remediação da Wave 0. A movimentação física do `SqlAlchemyUnitOfWork` e a criação de `adapters/outbound/db/` acontecem **junto com o primeiro repositório concreto, na Wave 2 (C06)** — não se move código agora para não tocar a fundação fora de escopo.
- **Consequências:** Convenção única para implementações de porta. A Wave 2 cria `adapters/outbound/db/` e move a UoW para lá no mesmo PR dos primeiros repositórios; o ponto de extensão de RLS (ADR-008) acompanha a UoW. O mapeamento do CLAUDE.md §5.1 ("DB (SQLAlchemy) → adapters/outbound/") passa a valer também para a UoW.

## ADR-018 — Arquitetura de autenticação e sessão (W1-C03)
- **Contexto:** A Wave 1 inicia a autenticação. Era preciso fixar o padrão de login/sessão sobre o Supabase Auth no App Router do Next, mantendo o backend stateless e "só verifica" (DAT §1.3, DP-1).
- **Decisão:** Login **direto Frontend ↔ Supabase Auth** via **`@supabase/ssr`** (`signInWithPassword`) — o `@supabase/auth-helpers` está deprecado. Sessão **stateless** em **cookies HTTP-only**, com três clients: **browser** (`createBrowserClient`), **servidor** (`createServerClient`, cookies via `next/headers`) e o helper `updateSession` chamado pelo **proxy** do App Router. Proteção **sempre** via `supabase.auth.getUser()` (valida no servidor de auth), **nunca** `getSession()`. O backend FastAPI **não** intermedia o login — apenas verifica o JWT (ADR-019). Destino pós-login = `/inicio` (placeholder, DP-4). Inatividade de 30 min no app (DP-3) **+** TTL do token no dashboard (ação do responsável).
- **Status:** **Aceita** (W1-C03) — DP-1/3/4 confirmados pelo dono do produto.
- **Consequências:** O `proxy.ts` desta wave **só faz refresh**; o RBAC (camada superior) entra no C05 sobre esta base (ADR-006, ADR-021). Rotas que emitem `Set-Cookie` de refresh recebem `Cache-Control: no-store` (cuidado de CDN, prompt §3.5). O reset de senha ficou fora do escopo (DP-5 — link inerte).

## ADR-019 — Verificação de JWT robusta a ES256(JWKS) + HS256 (W1-C03)
- **Contexto:** O C01/`.env.example` e a leitura inicial do DAT assumiam verificação **HS256** via `SUPABASE_JWT_SECRET`. Porém **projetos atuais do Supabase assinam o JWT com ES256 (assimétrico)** por padrão; verificar só com o segredo HS256 retorna 401 e quebra na rotação de chaves. Confirmado no projeto real `wmpxxrzbzqgsorjwczvz`: o JWKS publica **uma chave ES256 (EC P-256)** (DP-2, prompt §1.1).
- **Decisão:** O `JwtVerifier` (`adapters/inbound/http/auth.py`) verifica de forma **robusta a ambos**: lê o `alg` do header; **ES256/RS256 via JWKS** (cacheado pelo `PyJWKClient` nativo do PyJWT — sem nova dependência de runtime) e **HS256** (segredo) como **fallback**. Valida assinatura, **`aud="authenticated"`** e **`exp`**; rejeita `alg=none` e impede confusão de algoritmo (chave pública só p/ assimétrico; segredo só p/ HS256). Falha → **401 genérico** + log só do `error_type`. Endpoint de prova **`GET /auth/me`**. Variáveis: **`SUPABASE_JWKS_URL`** (derivado de `SUPABASE_URL` se vazio) + `SUPABASE_JWT_SECRET` (opcional). Dependência **`pyjwt[crypto]`**.
- **Status:** **Aceita** (W1-C03). **Corrige a premissa antiga** (HS256-only) do DAT/C01: o default vigente do Supabase é **ES256**; `SUPABASE_JWT_SECRET` deixa de ser obrigatório e vira fallback.
- **Consequências:** PyJWT continua **só verificando** (nunca emite — CLAUDE.md §11). A propagação de claims à RLS (ADR-008) se apoiará nesses claims verificados, no C05. O `Settings` do C01 ganhou os campos novos; o `.env.example` foi atualizado.

## ADR-020 — Fundação mínima da camada de animações no C03 (fronteira C03↔C19)
- **Contexto:** O C03 precisa de animações (entrada do login, microinterações) sobre tokens, mas a camada completa de animação é o C19 (Wave 6). O DAT §5.1 proíbe literais inline de duração/easing.
- **Decisão:** Trazer **agora** a fatia mínima: `apps/web/src/lib/motion/tokens.ts` (DURATION/EASING **exatos do DAT §5.1**) e `src/lib/motion/hooks.ts` (`useReducedMotion`, SSR-safe via `useSyncExternalStore`). As animações do login usam **Framer Motion sobre esses tokens** (DP-6 — instalado nesta wave), **só `transform`/`opacity`** (GPU), degradando para instantâneas com `prefers-reduced-motion`. O C19 **estende** (`<PageTransition>`, `<MotionModal>`, Toaster, etc.) sem reescrever a fundação.
- **Status:** **Aceita** (W1-C03) — DP-6 confirmado (usar Framer Motion).
- **Emenda (W1-C03, refino):** adicionado **`SPRING`** a `tokens.ts` (molas `interactive` e `parallax`) — extensão do DAT §5.1 para física de microinteração. Para **harmonia**, as interações (hover/press dos botões) usam a MESMA mola; o **contorno de foco dos campos faz fade-in/out** (overlay só de `opacity` — GPU, em vez de troca instantânea de borda). A imagem-herói ficou **estática** (parallax/zoom removidos a pedido do dono). Mantida a semântica DAT: entradas `emphasized`, saídas `exit`, fades `standard`; stagger único (0.07/0.06).
- **Consequências:** Tokens centralizados desde já evitam literais espalhados; o aviso de inatividade do C03 é um *notice* local, não o Toaster global do C19. O C19 herda `DURATION`/`EASING`/`SPRING` — vocabulário de motion único para todo o app.

## ADR-021 — Convenção do App Router: `proxy.ts` (Next 16) no lugar de `middleware.ts`
- **Contexto:** CLAUDE.md §5.4 e o prompt nomeiam `middleware.ts` (escritos para Next 14). O ambiente pina **Next 16.2.9** (ADR-014), que **deprecou a convenção `middleware`** em favor de **`proxy`** (mesma capacidade; `middleware.ts` ainda funciona mas emite aviso e será removido num major futuro).
- **Decisão:** Adotar **`apps/web/src/proxy.ts`** (exporta `proxy` + `config.matcher`) como a convenção do App Router. Onde os documentos dizem "middleware (camada superior)", **lê-se `proxy.ts`** no Next 16. O helper de refresh permanece em `lib/supabase/middleware.ts` (nome do `@supabase/ssr`, não é a convenção do Next). Confirmado pelo dono do produto nesta sessão.
- **Status:** **Aceita** (W1-C03). Emenda terminológica à ADR-006 (a camada superior do RBAC vive no `proxy.ts`).
- **Consequências:** Build sem aviso de depreciação e à prova do próximo major. O C05 acrescenta o enforcement de RBAC **dentro do `proxy.ts`** (após o refresh), lendo `lib/access-matrix.ts`. CLAUDE.md §5.1/§5.4 atualizados.

## ADR-022 — Fluxo de login adaptativo em rota única + herói com formato custom (refino W1-C03)
- **Contexto:** A 1ª entrega do C03 usava rotas separadas (`/bem-vindo` + `/login`) com **redirecionamento por viewport no cliente** — frágil (no mobile, sem o meta viewport correto, o breakpoint de desktop disparava e o **login aparecia antes** das boas-vindas) e com flash. O herói do desktop fora aproximado por `border-radius`, mas o Figma usa um **vetor custom** (retângulo arredondado com a borda direita inclinada para dentro).
- **Decisão:** (1) **Rota única `/login` adaptativa** (`<AuthFlow>`): desktop = split; mobile = **boas-vindas primeiro** e o formulário revelado por **troca de passo (estado)** ao clicar em "Entrar" — sem redirecionamento por viewport, com transição via `AnimatePresence`. `/` e `/bem-vindo` passam a **redirecionar para `/login`**. Adicionado `export const viewport` (width=device-width). (2) **Herói com o formato EXATO do Figma** via **máscara SVG** (`public/login-shape.svg` + `mask-image`), não mais `border-radius`. (3) **Animações** sobre os tokens: hover/press dos botões, fade do contorno no foco dos campos, entradas em *stagger* e transição boas-vindas→formulário — só `transform`/`opacity`, reduced-motion-aware. O **herói é estático** (apenas fade na entrada; parallax/zoom removidos a pedido do dono).
- **Status:** **Aceita** (W1-C03, refino pós-feedback do dono).
- **Consequências:** Emenda o desenho de rotas do DP-7/ADR-018 (as boas-vindas viram **passo do `/login`**, não rota própria). `Welcome`/`bem-vindo.module.css` removidos; `/bem-vindo` vira redirect. O C05 (RBAC) segue apoiado no `proxy.ts`. vitest 11/11 + Playwright 4/4 verdes; fidelidade reconferida por screenshots.

---

### Próximas decisões a confirmar (checklist vivo)
- [x] ADR-007 — validado: pooler/NullPool + caches off, suíte contra PostgreSQL 17.10 real (W0/C01).
- [ ] ADR-008 — desenhar propagação de claims/RLS por request (W1/C05). Ponto de extensão pronto em `SqlAlchemyUnitOfWork.begin()`.
- [ ] ADR-009 — confirmar plataformas de deploy com o responsável (CI/Dockerfile prontos e agnósticos).
- [x] ADR-010 — confirmado: `uv` 0.11 + `pnpm` 11 no ambiente alvo (W0/C01).
- [x] ADR-015 — keep-alive externo entregue e validado em execução real (W0/C02).
- [x] ADR-016 (parte CI) — **resolvido na remediação W0 (W0-A-002):** `develop` adicionado aos gatilhos de `push` do `ci.yml`. (Branch protection + PR continua opcional para o futuro.)
- [ ] ADR-016 (parte secret) — **ação do responsável (W0-A-001):** cadastrar o secret `KEEPALIVE_DATABASE_URL` no GitHub (Settings → Secrets and variables → Actions) e validar via `workflow_dispatch` — sem ele o cron diário do keep-alive falha e o Supabase fica desprotegido contra a pausa de 7 dias.
- [x] **ADR-018/019/020/021/022 (W1/C03)** — auth/sessão (`@supabase/ssr`, cookies, `getUser`), verificação de JWT **ES256/JWKS+HS256** (`/auth/me`), fundação de motion (C03↔C19), convenção `proxy.ts` e o **fluxo adaptativo em rota única + herói com formato custom** (refino): entregues, testados (backend 98% + web vitest/Playwright) e validados.
- [x] **ADR-009 (plataformas)** — responsável confirmou **Vercel (web) + Railway (API)** no W1-C03; on-prem futuro permanece revisável.
- [ ] **ADR-008** — desenhar a propagação de claims/RLS por request no **W1/C05**, agora sobre os claims já verificados pela ADR-019.
- [ ] **Responsável (DP-3):** ajustar o **TTL do access token** no dashboard do Supabase (Authentication → Sessions) coerente com a inatividade de 30 min.
