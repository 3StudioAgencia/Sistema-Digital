# SESSION_LOG.md

> Diário cronológico de sessões de trabalho. Cada sessão = um componente (em geral). Entrada mais recente no topo.
> Preenchido ao final de cada sessão pelo **Protocolo de Encerramento** (`CLAUDE.md §10`).

---

## Modelo de entrada (copiar para cada nova sessão)

```
## Sessão NN — AAAA-MM-DD — [Wave X / Componente CYY] Título

**Objetivo:** (o componente/escopo da sessão)

**Feito:**
- ...

**Decisões (ADRs):**
- ADR-XXX: ... (link/ref em DECISIONS.md)

**Testes / cobertura:**
- ...

**Pendências / em aberto:**
- [ ] ...

**Próximo passo:**
- (próximo componente conforme dependências do Backlog)

**Definition of Done:** (✅ atendida / ⚠️ parcial — detalhar)
```

---

## Sessão 06 — 2026-06-12 — [Wave 1 / W1-C04] Cadastro e Gestão de Usuários + App Shell

**Objetivo:** CRUD de usuários (RF-018, RF-020, US-015) com provisionamento via Supabase Auth Admin API, **primeira tabela/migration de domínio** (`usuarios`) e o **app shell** (sidebar + área de conteúdo) que hospeda toda a plataforma autenticada.

**Feito:**
- **Pré-flight** — limpeza de `__pycache__` órfãos (resíduo de tentativa anterior de C04) e commit do ajuste cosmético pendente do C03 (`login.module.css`).
- **Tokens do design** — o MCP do Figma estourou o limite do plano Starter; extração feita por **amostragem de pixel dos exports PNG 1:1** (Downloads: `Gerenciamento de usuários - admin (3).png` + `- Modal (1).png`; lossless → cores exatas) com 3 sondas Python/Pillow: paleta completa (`#eaeaea` shell r40, `#ff5959` Desativar, `#d7d7d7` controles, `#979797` divisores, scrim `rgba(0,0,0,.76)` medido, modal idêntico aos tokens `--auth-*` do C03), geometria (colunas da tabela com frações medidas, pills 56/29px, pitch 56px) e tipografia. Tokens centralizados em `globals.css` (`--app-*`).
- **Backend** — migration **`0002_usuarios`** (enums `setor_enum`/`localizacao_enum`, PK = UUID de `auth.users` 1:1, CHECK bidirecional RN-009, índices RNF-019, **RLS restritiva** aplicada e versionada em `migrations/rls/usuarios_baseline_restritiva.sql`; ciclo upgrade→downgrade→upgrade validado em PG 16 real porta 5433); domínio puro (`domain/usuarios.py`); portas `IdentityProviderPort`/`UsuariosRepositoryPort`; **`UsuariosService`** com provisionamento coordenado (**compensação** em falha parcial, **adoção de órfãos marcados** via `app_metadata.provisionado_por`, **fail-closed** nas mutações de status, salvaguarda do **último admin ativo**, sync de `app_metadata.{setor,administrador}` p/ o C05); adapter **`SupabaseAdminIdentityProvider`** (httpx, `sb_secret` server-only) + stand-in 503; endpoints `/usuarios` (listagem paginada server-side com busca escapada + filtros, criar, editar com e-mail imutável, desativar/reativar idempotentes, `/me`) com **guard mínimo de admin**; task **`bootstrap_admin`**; `.env.example` com `SUPABASE_SECRET_KEY`.
- **Frontend** — **app shell** no grupo `(app)` (`AppShell` + `Sidebar` com indicador ativo via `layoutId`, busca inerte, rodapé via `GET /usuarios/me` com fallback gracioso; placeholders DP-6; transição de conteúdo por rota); **Gerenciador de usuários** fiel ao design (debounce 300ms, filtros server-side, scroll infinito na área da tabela, mutações em memória); **`MotionModal`** reutilizável (DAT §5.2, focus trap, reduced-motion) + form Novo/Editar (validação em tempo real, localização condicional p/ Vendedor, 409 inline) + confirmação de status; **toasts** (`useToast`); **responsivo** DP-7 (drawer/cards/folha, ≥44px). Rotas `/`, `/login`, `/inicio` → `/usuarios`; `AuthProof`/`ApiStatus` removidos (mortos).
- **Fidelidade visual** — verificada por rota de preview temporária + screenshot Playwright **1920×1080 comparado pixel a pixel** com os exports (cores idênticas; scrim `#343434` vs `#333333`); preview removido antes do commit.
- **Qualidade** — api: ruff + mypy strict verdes, **201 testes** (90% cobertura) incl. compensação com PG real e estrutura da migration; web: eslint + prettier + build verdes, **50 testes** vitest + Playwright 8/8 (5 live gated); **revisão adversarial multi-agente** (5 dimensões × céticos) sobre os dois commits.
- **Docs** — `docs/usuarios.md`, `docs/app-shell.md`; CLAUDE.md §2.1/§5.5-5.6/§6/§9; README (deploy confirmado, setup C04, roadmap); CHANGELOG (duas seções `### Fixed` consolidadas).

**Decisões (ADRs):**
- **ADR-023** — DP-1: modelo **Setor × Administrador ortogonal** (o design governa) + releitura da Matriz §7 p/ o C05; refletida em CLAUDE.md §2.1.
- **ADR-024** — DP-2: `usuarios` 1:1 com `auth.users` (PK = UUID do auth, sem FK física) + schema/índices.
- **ADR-025** — DP-3/DP-4: provisionamento via Admin API (httpx, sem SDK), compensação/adoção de órfãos, `SUPABASE_SECRET_KEY` server-only, desativar = ban + `ativo=false` (US-015), e-mail imutável.
- **ADR-026** — app shell como layout do grupo `(app)` (DP-6/DP-7/DP-9: lucide-react, wordmark do C03, status no 2º dropdown, scroll infinito, "Satus"→"Status").
- **ADR-027** — DP-5: guard mínimo de admin agora + RLS provisória + `app_metadata`; RBAC completo no C05.
- **ADR-028** — DP-8: `MotionModal`/toasts criados já no contrato do C19 (que generaliza sem reescrever).

**Testes / cobertura:**
- api: `uv run pytest` → **201 passed** (REQUIRE_DB_TESTS=1, PG 16 real), cobertura **90%** (fail_under 80); ruff + mypy strict limpos.
- web: `pnpm test` → **50 passed** (10 arquivos); `pnpm test:e2e` → 8 passed + 5 live-gated; lint/build/format verdes.

**Pendências / em aberto:**
- [ ] **Responsável:** cadastrar `SUPABASE_SECRET_KEY` no backend (Railway/.env), configurar a **política de senha** no dashboard (min. 8, letras+dígitos), rodar `alembic upgrade head` no Supabase real e o `bootstrap_admin` do primeiro administrador.
- [ ] Visibilidade dos itens de menu por perfil + enforcement de rota + RLS por perfil + Custom Access Token Hook → **C05**.
- [ ] Busca global da sidebar (inerte até a Wave 2); reset/troca de senha (componente futuro); "página inicial do perfil" (C05).
- [ ] Itens herdados: W0-A-001 (`KEEPALIVE_DATABASE_URL`), TTL do access token (DP-3 do C03), W0-A-018 (mover `SqlAlchemyUnitOfWork` p/ `adapters/outbound/db/` no C06).

**Próximo passo:**
- **W1-C05 · Controle de Acesso por Perfil — Matriz RBAC** (access-matrix.ts + enforcement no proxy + políticas RLS por perfil + Custom Access Token Hook, sobre o `app_metadata` já gravado).

**Definition of Done:** ✅ atendida — testes (incl. provisionamento/RN-009/RN-010/idempotência), migration versionada e documentada, RLS versionada em `migrations/rls/`, sem erros de console/log crítico, docs do módulo, animações validadas com `prefers-reduced-motion`, sem segredos versionados, árvore limpa.

**Pós-entrega (mesma sessão):**
- **Suporte live ao dono:** o 500 em `/usuarios` no ambiente real era a migration `0002` não aplicada no Supabase — `alembic upgrade head` executado lá + primeiro admin provisionado por upsert direto (a `SUPABASE_SECRET_KEY` ainda não está no `.env`; sem ela, criar/editar/desativar respondem 503 — pendência do responsável).
- **Revisão adversarial concluída** (38 agentes; 27 confirmados/6 refutados) → correções em dois commits `fix(w1-c04)`: concorrência no backend (adoção de órfão com idade mínima, lock otimista + 409, RN-010 com advisory lock transacional, idle-in-transaction, bootstrap reordenado, migration **`0003`** trancando `alembic_version` no PostgREST — aplicada no Supabase real, `/docs` off em produção, JWKS timeout) e robustez no frontend (loop infinito do scroll, corrida de paginação, timeout combinado, modais durante submit, drawer back/forward, signOut, motion/ARIA/touch). api: **207 testes**, 90%; web: **50 testes**.
- **Fidelidade (feedback do dono):** sidebar/conteúdo escalados ao quadro de 1080px do Figma via unidade `--u` — pixel a pixel em 1080 (±2px), proporcional em janelas menores.
- Refutados pela verificação cética (sem ação): cap da busca por e-mail, acesso do desativado até o TTL (mitigado pelo ban+revogação), `layoutId` duplicado desktop/drawer, falta de `error.tsx` no grupo, ILIKE sem índice dedicado (escala ~30 usuários).

---

## Sessão 05 — 2026-06-11 — [Wave 1 / W1-C03] Tela de Login e Sessão

**Objetivo:** Autenticação por e-mail/senha (Supabase Auth), sessão stateless em cookie + refresh, encerramento por inatividade de 30 min, verificação de JWT no backend e as **três telas do design** — primeiro componente da Wave 1.

**Feito:**
- **Backend** — `JwtVerifier` (`adapters/inbound/http/auth.py`): **ES256 via JWKS** cacheado (`PyJWKClient`) + **HS256 fallback**, valida `aud="authenticated"`/`exp`, rejeita `alg=none` e confusão de algoritmo; **`GET /auth/me`** (prova). `Settings` ganhou `SUPABASE_JWKS_URL`/`effective_jwks_url`; dependência `pyjwt[crypto]`. 18 testes offline; ruff + mypy + pytest verdes (cobertura **98%**, 104 passed/7 skipped).
- **Frontend** — clients **`@supabase/ssr`** (browser/servidor) + `updateSession` + **`src/proxy.ts`** (só refresh; `getUser()`); **três telas** em CSS Modules fiéis ao Figma (`/login` adaptativa desktop-split/mobile, `/bem-vindo`, `/inicio` placeholder com `AuthProof → /auth/me` + Sair); **erro de login genérico**; **inatividade 30 min** (`InactivityGuard`); fundação de **motion** (tokens DAT §5.1 + `useReducedMotion`) com **Framer Motion** (transform/opacity, reduced-motion-aware). **Inter** self-hospedada; herói **17,8 MB → 540 KB**. **vitest 11/11** + **Playwright 4/4** (+1 *live* gated); `pnpm lint`/`build` verdes; fidelidade conferida por screenshots.
- **Docs** — `docs/auth.md`; `.env.example` (api/web) atualizados.
- **Refino (pós-feedback do dono):** (1) fluxo mobile corrigido — **boas-vindas primeiro**, login revelado ao clicar em "Entrar", em **rota única `/login`** (`<AuthFlow>`, troca de passo, sem redirect por viewport); `/` e `/bem-vindo` redirecionam para `/login`; `export const viewport` adicionado. (2) Herói do desktop com o **formato custom EXATO do Figma** (máscara SVG). (3) Animações (fade do contorno no foco dos campos, hover/press dos botões, transição boas-vindas→form; **imagem-herói estática** — parallax/zoom removidos a pedido do dono). (4) **Harmonização do motion:** contorno do input com **fade-in/out** no foco (overlay de opacity) e **mola única `SPRING`** (`tokens.ts`) para todas as interações + stagger/easing consistentes (emenda ADR-020). `Welcome`/`bem-vindo.module.css` removidos. vitest 11/11 + Playwright 5/5 verdes; screenshots reconferidos. **ADR-022.**

**Decisões (ADRs):**
- **ADR-018** (auth/sessão), **ADR-019** (verificação JWT ES256/JWKS+HS256 — corrige a premissa HS256), **ADR-020** (fundação de motion C03↔C19), **ADR-021** (`proxy.ts` no Next 16), **ADR-022** (fluxo adaptativo em rota única + herói custom + animações, refino); **emendas** ADR-014 (Inter local) e ADR-009 (Vercel + Railway confirmados).
- **Pontos de decisão (respostas do dono):** DP-1 ✓ · DP-2 = ES256/JWKS+HS256 + publishable moderna · DP-3 ✓ · DP-4 = `/inicio` · DP-5 = link inerte · DP-6 = instalar Framer Motion · DP-7 ✓ (breakpoint 768px) · DP-8 = tokens via link do Figma.

**Testes / cobertura:**
- Backend: **104 passed / 7 skipped (@db)**, cobertura **98%**. Web: **vitest 11/11**, **Playwright 4/4** (+1 *live* gated). ruff/mypy/eslint/`next build` verdes.

**Pendências / em aberto:**
- [ ] **Reset de senha** (fora do escopo do C03 — DP-5; link inerte por ora).
- [ ] **Caminho feliz E2E autenticado**: atrás de `E2E_LIVE` (requer usuário semeado + API rodando; a checagem `getUser` do servidor não é route-mockável). Sucesso já coberto pelo teste de componente.
- [ ] **Responsável:** ajustar o **TTL do access token** no dashboard (DP-3); cadastrar `KEEPALIVE_DATABASE_URL` (W0-A-001, herdada).
- [ ] Node Figma `70:171` (login mobile) reproduzido por tokens compartilhados + PNG anexado (rate limit do Figma Starter) — revalidar se necessário.

**Próximo passo:**
- **W1-C04 · Cadastro e Gestão de Usuários.**

**Definition of Done:** ✅ (subconjunto aplicável ao C03): testes verdes; sem erro de console/log crítico; docs do módulo (`docs/auth.md`); error handling (401 genérico, error boundaries herdados); animações validadas com `prefers-reduced-motion`; sem segredos versionados. RLS/migrations **não se aplicam** ao C03 (tabelas de auth são do Supabase).

---

## Sessão 04 — 2026-06-11 — [Wave 0 / W0-REMEDIATION] Remediação da Wave 0

**Objetivo:** Corrigir os achados da auditoria (`docs/audits/wave-0-audit.md`) por severidade/dependência, com teste por correção e **gate de re-verificação**, sem regressão nem escopo novo (escopo de `PROMPTS/W0-REMEDIATION-remediacao.md`).

**Feito:**
- **29/29 achados endereçados** (0 Blocker · 0 High · 2 Medium · 16 Low · 11 Nit): **26 Resolvidos**, **1 Resolvido documental** (W0-A-018 → ADR-017, código na Wave 2), **1 Ação do responsável** (W0-A-001), **1 Parcial + dívida** (W0-A-029).
- **Medium:** W0-A-002 — CI dispara em push para `develop` (decisão do responsável); W0-A-001 — o responsável **cadastrará o secret** `KEEPALIVE_DATABASE_URL` (workflow mantido fail-loud, correto após o secret existir).
- **Robustez/observabilidade:** log da causa no readiness/`ping`/storage (003), R2 com timeouts (004), keep-alive sem vazar credencial na carga de config (005), `LOG_LEVEL` validado no boot (013), hermeticidade total da suíte vs. env de shell (012), downgrade defensivo da baseline (014).
- **Segurança HTTP:** guarda CORS curinga (015), security headers nosniff/no-store (016), whitelist de `X-Request-ID` (023), SHA-pinning de actions + Dependabot (008).
- **Frontend:** validação de shape + `error.tsx` (017). **Workflows:** permissions/concurrency/format:check/--no-dev (009/010/011/024). **Docs/ADRs:** emenda ADR-013 (007), ADR-017 (018), keep-alive §6 (006), `.env.example` (020/021), CLAUDE §5.1 (019), README (028); nits (022/025/026/027/029).
- Suíte **70 → 88 testes**, cobertura **100%** mantida. Log completo em `docs/audits/wave-0-remediation.md`.

**Decisões (ADRs):**
- **ADR-017** (novo): lar das implementações de porta de DB = `adapters/outbound/db/` (UoW move na Wave 2). **ADR-013 emendada** (catch-all = `ErrorHandlingMiddleware` interno ao CORS). **ADR-016** checklist: parte CI resolvida (`develop` nos gatilhos de push); secret = ação do responsável.

**Testes / cobertura:**
- **Gate de re-verificação (§5) VERDE:** ruff + ruff format + mypy strict; ciclo Alembic `upgrade→downgrade→upgrade` (PostgreSQL 16.9 real, porta 5433); **88 passed, cobertura 100%** (`REQUIRE_DB_TESTS=1`); keep-alive `exit 0`; domínio limpo; varredura de segredos limpa; `pnpm install/lint/format:check/build` verdes; lockfiles versionados.

**Pendências / em aberto:**
- [ ] **W0-A-001 (responsável):** cadastrar `KEEPALIVE_DATABASE_URL` no GitHub (Settings → Secrets and variables → Actions) e validar via `workflow_dispatch`. Até lá o cron diário falha e o Supabase fica desprotegido.
- [ ] **Dívida W0-A-029:** pinar as imagens base do `Dockerfile` por digest ao definir a plataforma de deploy (ADR-009).
- [ ] **W0-A-018:** mover `SqlAlchemyUnitOfWork` para `adapters/outbound/db/` na Wave 2 (C06).
- [ ] (Herdada) `apps/web/public/` untracked (assets do W1-C03); confirmar plataformas de deploy (ADR-009).

**Próximo passo:**
- **Wave 1 · W1-C03 · Tela de Login e Sessão** na branch `develop`.

**Definition of Done:** ✅ Gate verde; correções testadas e aderentes ao `CLAUDE.md`; sem regressão; sem segredos versionados; protocolo de encerramento executado.

---

## Sessão 03 — 2026-06-11 — [Wave 0 / W0-AUDIT] Auditoria read-only da Wave 0

**Objetivo:** Auditoria independente e somente-leitura dos componentes W0-C01 e W0-C02 (escopo de `PROMPTS/W0-AUDIT-auditoria.md`) — inspecionar, verificar e relatar, **sem corrigir nada**.

**Feito:**
- Verificações executáveis contra **PostgreSQL 17.10 real** (binários portáteis, porta 5433; env sobrescrita — Supabase real intocado): ruff + ruff format ✅ · mypy strict ✅ · pytest offline (70 passed/6 skip, 98,81%) ✅ · pytest com `REQUIRE_DB_TESTS=1` (**76 passed, cobertura 100%**) ✅ · ciclo Alembic `upgrade→downgrade→upgrade` em banco limpo ✅ · keep-alive sucesso (`exit 0`) e falha controlada (`exit 1`, sem vazar credencial) ✅ · smoke test da API (`/health` 200, `/health/ready` 503 `degraded` sem R2, `/docs` 200, `X-Request-ID` propagado) ✅ · pnpm lint/build ✅ · varredura de segredos limpa ✅.
- Auditoria multi-agente: 12 auditores por dimensão (§4.1–4.12 + 2 varreduras extras) × verificação adversarial cética de cada achado (48 agentes). 36 achados brutos → **29 únicos** após deduplicação.
- **Relatório entregue:** `docs/audits/wave-0-audit.md` (matriz de conformidade C01 §5/C02 §5/DoD, 29 achados com ID estável `W0-A-001`…`W0-A-029`, lista priorizada de remediação, apêndice de evidências).

**Veredito:** **Wave 0 apta a servir de base à Wave 1 — continuidade NÃO bloqueada.** Contagem: **0 Blocker · 0 High · 2 Medium · 16 Low · 11 Nit**. Os 2 Medium são handoffs operacionais já registrados no ADR-016 e ainda não executados: **W0-A-001** (cron do keep-alive armado na branch padrão **sem** o secret `KEEPALIVE_DATABASE_URL` → falha diária + Supabase real desprotegido, pausa possível ~2026-06-18) e **W0-A-002** (CI não dispara em push para `develop` — o HEAD da branch de integração nunca rodou no CI do GitHub).

**Pendências / em aberto:**
- [ ] Executar a **sessão de remediação da Wave 0** consumindo `docs/audits/wave-0-audit.md` (ordem sugerida no §5 do relatório; começar por W0-A-001/W0-A-002).

**Próximo passo:**
- **Sessão de remediação da Wave 0** consumindo `docs/audits/wave-0-audit.md`. (A Wave 1 / W1-C03 segue na fila após a remediação dos itens Medium.)

**Definition of Done:** N/A (sessão de auditoria — protocolo leve do prompt W0-AUDIT §8: relatório salvo + esta entrada; `CHANGELOG.md`/`DECISIONS.md`/código intocados por regra).

---

## Sessão 02 — 2026-06-11 — [Wave 0 / Componente C02] Cron Job de Keep-Alive

**Objetivo:** Entregar o keep-alive que impede a pausa do Supabase no free tier (>7 dias sem requisições): rotina read-only de *ping*, workflow agendado, alerta de falha e docs — reutilizando a infra do C01 (escopo de `PROMPTS/W0-C02-keep-alive.md`).

**Feito:**
- **Consolidação DRY:** extraída `fetch_db_time()` em `src/infrastructure/database.py` (núcleo único do *ping*, `SELECT now()`); `ping()` do readiness passou a envelopá-la (contrato `-> bool` intacto); novo `create_direct_engine()` para a conexão *one-shot* na direta/sessão (5432).
- **Rotina** `src/tasks/keep_alive.py` (`uv run python -m src.tasks.keep_alive`): conexão curta via `MIGRATIONS_DATABASE_URL`, log JSON estruturado (`event`/`status`/`latency_ms`/`db_time`/`correlation_id`/`env`), exit 0/≠0, erro sem vazar credencial (só `error_type`).
- **Workflow** `.github/workflows/keep-alive.yml`: `schedule 0 9 * * *` (06:00 BRT) + `workflow_dispatch`, `concurrency`, `timeout-minutes: 5`, `permissions: contents: read`, secret `KEEPALIVE_DATABASE_URL`, alerta opcional `if: failure()` + `ALERT_WEBHOOK_URL` (pulado sem o secret).
- **Testes:** offline (`tests/unit/test_keep_alive.py` — campos do log, exit codes, prova de não-vazamento de senha) e `@db` (`tests/integration/test_keep_alive.py` — sucesso real). Fix de hermeticidade do `test_main.py` (`chdir(tmp_path)`) e *fixture* autouse `_isola_logging_global` em `conftest.py`.
- **Docs:** `docs/keep-alive.md` (racional, cadência, ligar em produção, teste manual, alternativa Cloudflare Worker Cron) + link em `docs/setup-infra.md`.
- **Validação em execução real:** *ping* read-only ao **Supabase real** → `exit 0`, `status="ok"`, `db_time` real, `latency_ms≈331ms`; falha com credencial inválida → `exit 1`, `status="error"`, sem vazar a senha.
- Revisão adversarial multi-agente (6 dimensões × verificação cética) sobre o change set.
- **Publicado no GitHub:** repositório [`3studioagn/Sistema-Digital`](https://github.com/3studioagn/Sistema-Digital) criado; remote `origin` configurado; branches `main` (estável) e `develop` (integração, **padrão**) enviadas em `abc293c` via Git Credential Manager (ambiente sem `gh`).

**Decisões (ADRs):**
- **ADR-015** (keep-alive externo; scheduler primário GitHub Actions; conexão direta para o *one-shot*; cadência diária; alerta nativo + webhook opcional; alternativa Cloudflare documentada). **Nota:** o prompt referenciava "ADR-012", mas 012–014 já existiam (W0-C01) → adotado o próximo livre, **015** (divergência registrada, `CLAUDE.md §2.1`).

**Testes / cobertura:**
- **70 passaram, 6 skip** (`@db`, sem Postgres local) offline; cobertura **98.81%** (linhas restantes são caminhos de sucesso `@db`, cobertos no CI). `ruff`, `ruff format` e `mypy --strict` verdes. Sem segredos versionados.

**Pendências / em aberto:**
- [x] Push para o remoto — **feito**: `3studioagn/Sistema-Digital` (branches `main` + `develop`). Resolve também a pendência herdada do C01.
- [ ] **Ligar keep-alive em produção:** cadastrar o secret `KEEPALIVE_DATABASE_URL` (e opcional `ALERT_WEBHOOK_URL`) em **Settings → Secrets and variables → Actions** — o cron diário (06:00) **falha** sem ele; validar via `workflow_dispatch`.
- [ ] **CI em `develop`:** `ci.yml` só dispara em `main` + PRs; pushes diretos em `develop` não acionam a CI. Decidir adicionar `develop` aos gatilhos de push **ou** adotar fluxo por PR (ADR-016).
- [ ] **`apps/web/public/`** (`login-bg.png` 18 MB + `logo-3studio.svg`) untracked — decidir **Git LFS** vs commit normal; pertence ao W1-C03.
- [ ] (Opcional) Branch padrão no GitHub = `develop`; trocar para `main` em Settings → Branches se preferir.
- [ ] (Herdada) Confirmar plataformas de deploy (ADR-009).

**Próximo passo:**
- **Wave 1 · W1-C03 · Tela de Login e Sessão** (primeiro componente da Wave 1; Wave 0 concluída). Trabalhar na branch `develop`.

**Definition of Done:** ✅ atendida no subconjunto aplicável (testes ≥ piso, observabilidade/log estruturado, error handling com exit code + alerta, docs do módulo, sem segredos versionados, idempotência N/A — operação read-only sem escrita).

---

## Sessão 01 — 2026-06-10 — [Wave 0 / Componente C01] Configuração de Infraestrutura

**Objetivo:** Fundação completa do monorepo: backend FastAPI hexagonal, Alembic, storage R2, observabilidade, frontend Next.js, CI e docs de provisionamento (escopo do prompt `PROMPTS/W0-C01-infraestrutura.md`).

**Feito:**
- Monorepo inicializado (git, `.gitignore`, `.editorconfig`, `.gitattributes`, `docker-compose.yml` com Postgres 17 + banco de teste isolado).
- `apps/api`: arquitetura Ports & Adapters completa (config → logging → database → porta de storage → adapter R2 → middleware/erros → health → app factory → composition root). Alembic async + baseline `0001` (pgcrypto) + `migrations/rls/README.md`. Dockerfile multi-stage non-root. `.env.example` integral.
- `apps/web`: Next 16.2.9 (App Router, TS strict, CSS Modules), página de status com consulta única ao readiness, client Supabase mínimo lazy, ESLint+Prettier, build hermético.
- CI GitHub Actions (api: ruff/mypy/alembic↑↓/pytest com Postgres service; web: lint/build) + deploy documentado parametrizável.
- `docs/setup-infra.md` (provisionamento Supabase/R2 + checklist de aceitação).
- Validação contra **PostgreSQL 17.10 real** (binários portáteis, porta 5433): 66 testes verdes com `REQUIRE_DB_TESTS=1`, ciclo `alembic upgrade head → downgrade base → upgrade head` via CLI em banco limpo, API de pé com `/health` 200, `/health/ready` 503 `degraded` (storage down sem R2 — degradação esperada) e `/docs` servindo OpenAPI.
- Revisão adversarial multi-agente (6 dimensões × verificação cética) sobre os critérios de aceitação, regra hexagonal, segredos, escopo, CI e ADR-007.

**Decisões (ADRs):**
- ADR-007 → **Aceita** (validada em execução); ADR-010 → **Aceita** (uv/pnpm confirmados); ADR-003 anotada com as versões pinadas.
- **ADR-012** (porta de storage síncrona + threadpool), **ADR-013** (catch-all no middleware de request-id, envelope canônico de erro), **ADR-014** (Next 16 pinado, build hermético) — novas.

**Testes / cobertura:**
- 66 testes (unit + integração), **100% de cobertura** da camada (piso configurado: 80%). `ruff` e `mypy --strict` verdes. `pnpm lint`/`pnpm build` verdes. Sem warnings na suíte.
- Testes `@db` fazem skip sem Postgres local e FALHAM no CI se o banco sumir (`REQUIRE_DB_TESTS=1`).

**Pendências / em aberto:**
- [x] Provisionar Supabase + R2 — **já existiam** (verificado via MCP em 2026-06-10): projeto `rastreio-provas-digitais` (ref `wmpxxrzbzqgsorjwczvz`, sa-east-1, PG 17, `pgcrypto` instalado) e bucket R2 `rastreio-provas-digitais`. `.env` locais preenchidos com URL e chave publishable.
- [x] Senha do banco preenchida e validada (2026-06-10). Descoberta: conexão direta é IPv6-only → `MIGRATIONS_DATABASE_URL` ajustada para o **session pooler** (aws-1:5432, emenda na ADR-007). `alembic upgrade head` aplicado no Supabase real (`0001 (head)`); **readiness 200 com `database: ok` + `storage: ok`** — infraestrutura real completa.
- [x] API Token do R2 criado e validado (2026-06-10): `storage: ok` no readiness e roundtrip real upload→download→delete via `StoragePort` (roteiro `docs/setup-infra.md` §5) executado com sucesso contra o bucket `rastreio-provas-digitais`.
- [ ] Confirmar plataformas de deploy com o responsável (ADR-009) e ligar os jobs comentados no `ci.yml`.
- [ ] Push para o remoto `rastreio-provas-digitais` quando o repositório for criado no GitHub.

**Próximo passo:**
- **W0-C02 · Cron Job de Keep-Alive** (depende do C01, agora concluído).

**Definition of Done:** ✅ atendida no subconjunto aplicável à infraestrutura (testes ≥ piso, migrations versionadas e aplicáveis, sem erros de console/log crítico, docs por módulo, RLS = política versionada [implementação na W1], observabilidade e error handling validados; itens de UI/animação/N+1 não se aplicam a este componente).

---

## Sessão 00 — 2026-06-09 — Bootstrap do projeto (Engenharia de Prompts)

**Objetivo:** Analisar os documentos de especificação, estabelecer a fundação de contexto e preparar a execução da Wave 0.

**Feito:**
- Análise integral de: Requisitos v1.0, Backlog v1.0, DAT v3.0 e UML v3.0.
- Criação dos documentos de contexto na raiz: `CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`.
- Definição da hierarquia de fontes da verdade e mapeamento das divergências entre as versões dos documentos (`CLAUDE.md §2.1`).
- Consolidação do glossário de domínio canônico (14 estados, 4 rotas, enums) em `CLAUDE.md §6`.
- Baseline de ADRs (001–011) em `DECISIONS.md`.
- Preparação do prompt de execução do **W0-C01 — Configuração de Infraestrutura**.

**Decisões (ADRs):**
- ADR-001 a ADR-006 — Aceitas (monorepo, hexagonal, stack, rota manual/imutável, máquina de estados em código, RBAC em profundidade).
- ADR-007 a ADR-010 — Propostas (conexão Supabase, RLS por request, deploy, gerenciadores de pacote) — a confirmar nas waves indicadas.
- ADR-011 — Aceita (tratamento dos documentos desatualizados; UML a regenerar; DAT §6 ignorado).

**Pendências / em aberto:**
- [ ] Confirmar plataformas de deploy (ADR-009) com o responsável.
- [ ] Validar estratégia de conexão Supabase (pooler de transação + NullPool) em execução (ADR-007, na W0-C01).
- [ ] Regenerar UML alinhado à v1.0 — após a Wave 2.

**Próximo passo:**
- Executar **W0-C01 — Configuração de Infraestrutura** (prompt em `prompts/wave-0/W0-C01-infraestrutura.md`).

**Definition of Done:** N/A (sessão de preparação; nenhum componente de código fechado ainda).
