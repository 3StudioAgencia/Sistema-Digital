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
- [ ] Preencher a **senha do banco** nos dois `DATABASE_URL`/`MIGRATIONS_DATABASE_URL` de `apps/api/.env` (cofre do responsável; ou reset no Dashboard) e rodar `uv run alembic upgrade head` contra o Supabase.
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
