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
- **Status:** Aceita.
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
- **Decisão (proposta):** Runtime da aplicação usa o **pooler de transação (6543)** com `asyncpg` + `statement_cache_size=0` + SQLAlchemy `NullPool` (pooling delegado ao PgBouncer) → seguro para escala horizontal. **Migrations (Alembic)** usam a **conexão direta/sessão (5432)**, pois DDL exige recursos de sessão.
- **Status:** **Proposta** — confirmar e validar na Wave 0 / C01.
- **Consequências:** Duas URLs de conexão (`DATABASE_URL` runtime vs `MIGRATIONS_DATABASE_URL`). Documentar ambas em `.env.example`.

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
- **Decisão (proposta):** **`uv`** para o backend (resolução rápida, `pyproject.toml`, lockfile) e **`pnpm`** para o frontend. Sem orquestrador de monorepo na v1.0.
- **Status:** **Proposta** — confirmar na Wave 0 / C01 (fallback: `pip`+venv / `npm` se necessário no ambiente alvo).
- **Consequências:** Lockfiles versionados; comandos padronizados no README e CLAUDE.md §9.

## ADR-011 — Tratamento dos documentos desatualizados (UML/DAT v3.0)
- **Contexto:** UML v3.0 desatualizado (2 rotas / ~10 estados / rota inferida); DAT v3.0 tem referências cruzadas a "Requisitos v4.0" e uma estratégia de migração (DAT §6) inaplicável a greenfield.
- **Decisão:** **Requisitos v1.0 + Backlog v1.0 = fonte única** de negócio/escopo. DAT v3.0 vale **apenas** para stack/padrões, com as ressalvas de CLAUDE.md §2.1. **DAT §6 (migração) é IGNORADO.** O **UML será regenerado** (4 rotas, 14 estados, rota manual/imutável) como tarefa de documentação após a Wave 2.
- **Status:** Aceita.
- **Consequências:** Evita que o Claude Code reintroduza o modelo antigo. Divergências novas devem ser registradas como ADR aqui.

---

### Próximas decisões a confirmar (checklist vivo)
- [ ] ADR-007 — validar pooler de transação + NullPool em execução (W0/C01).
- [ ] ADR-008 — desenhar propagação de claims/RLS por request (W1/C05).
- [ ] ADR-009 — confirmar plataformas de deploy com o responsável.
- [ ] ADR-010 — confirmar `uv`/`pnpm` no ambiente alvo.
