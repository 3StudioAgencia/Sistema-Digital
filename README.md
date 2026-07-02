# Rastreio de Provas Digitais

Plataforma web da **3Studio** para controle e rastreabilidade do fluxo físico-digital de provas de impressão — da criação à conclusão na clicheria — com máquina de estados de **14 estados** em **4 rotas**, RBAC em duas camadas e identificação por QR Code (câmera) com fallback de digitação manual.

- **Versão (baseline):** v1.0 — Junho/2026
- **Custo-alvo:** R$ 0 (infra local + Cloudflare R2)
- **Documentação de contexto:** [`CLAUDE.md`](./CLAUDE.md) · [`DECISIONS.md`](./DECISIONS.md) · [`CHANGELOG.md`](./CHANGELOG.md) · [`SESSION_LOG.md`](./SESSION_LOG.md)

> ⚠️ **Migração em curso (Sessão 30 · 2026-07-02): Supabase → infra LOCAL.** O projeto **saiu do Supabase**. **Etapa 1 (banco):** PostgreSQL **local** (nativo, porta 5432; migrations Alembic idênticas ao schema anterior). **Etapa 2 (auth):** **autenticação própria no FastAPI** — JWT **ES256** emitido pelo backend, refresh rotativo persistido/revogável (`auth_sessions`), senhas em **argon2id** (`auth_credentials`), cookies **httpOnly**. **Etapa 3 (pendente):** live-update próprio (SSE/WS) para repor o Realtime — hoje **neutralizado** (dashboard usa carga SSR). Notas de Auth/Usuários abaixo que citam Supabase valem como **histórico**; a operação atual é a desta migração. Ver ADR-107..113 e `SESSION_LOG.md` (Sessão 30).

---

## Stack

| Camada | Tecnologias |
| --- | --- |
| **Frontend** | Next.js (App Router, ≥14) · TypeScript (strict) · CSS Modules · Framer Motion · Recharts · html5-qrcode · qrcode.react · react-signature-canvas |
| **Backend** | Python 3.12 · FastAPI (async) · SQLAlchemy 2.0 async · Pydantic v2 · Alembic · PyJWT (verifica **e emite** o JWT ES256 próprio — Sessão 30) · argon2-cffi (argon2id) |
| **Banco / Auth / Realtime** | PostgreSQL **local** (nativo, porta 5432) · **Auth própria** no FastAPI (ES256 + refresh rotativo + cookies httpOnly) · Realtime **neutralizado** (SSE/WS próprio → etapa 3) · Row Level Security |
| **Storage** | Cloudflare R2 (S3-compatível) · boto3 |
| **Testes** | pytest · pytest-asyncio · httpx · Playwright |

> A stack segue o Documento de Arquitetura Técnica (DAT). As **regras de negócio e o escopo** seguem os documentos de **Requisitos v1.0** e **Backlog v1.0**. Em caso de divergência entre documentos, ver `CLAUDE.md §2`.

---

## Estrutura do repositório (monorepo)

```
rastreio-provas-digitais/
├── apps/
│   ├── api/      # Backend FastAPI (Ports & Adapters)
│   └── web/      # Frontend Next.js (App Router)
├── docs/         # Documentação técnica viva
├── .github/      # CI/CD
└── CLAUDE.md · DECISIONS.md · CHANGELOG.md · README.md · SESSION_LOG.md
```

Detalhamento completo da arquitetura em [`CLAUDE.md §5`](./CLAUDE.md).

---

## Pré-requisitos

- **Node.js** LTS + **pnpm**
- **Python** 3.12 (piso 3.11) + **uv**
- **PostgreSQL** local (nativo, porta 5432 — cria os bancos `rastreio` e `rastreio_test`). O `docker compose up -d db` segue disponível como alternativa; a suíte de testes roda offline sem Postgres.
- **Par de chaves EC P-256** para o JWT ES256 próprio (`AUTH_JWT_PRIVATE_KEY`/`AUTH_JWT_PUBLIC_KEY`, PEM em base64) — a privada só no backend; a pública também no `apps/web/.env` (server-only) para a verificação no proxy/SSR.
- Conta **Cloudflare R2** (bucket) — provisionamento em [`docs/setup-infra.md`](./docs/setup-infra.md). *(Supabase não é mais necessário — ver banner acima.)*

> **Plataformas de deploy confirmadas:** **Vercel** (web) + **Railway** (API), on-prem futuro revisável (ADR-009, *Aceita*); gerenciadores de pacote `uv`/`pnpm` confirmados (ADR-010). Ver `DECISIONS.md`.

---

## Setup local

```bash
# 1. Variáveis de ambiente (preencher a partir dos exemplos)
cp apps/api/.env.example apps/api/.env       # DATABASE_URL/MIGRATIONS_DATABASE_URL → Postgres local;
cp apps/web/.env.example apps/web/.env        #   AUTH_ISSUER + AUTH_JWT_PRIVATE_KEY/PUBLIC_KEY (ES256);
                                              #   web: BACKEND_INTERNAL_URL + AUTH_JWT_PUBLIC_KEY (server-only)

# 2. Postgres local (nativo na porta 5432 — bancos `rastreio` e `rastreio_test`).
#    Alternativa em container: docker compose up -d db

# 3. Backend
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload     # http://localhost:8000  (/docs, /health)

# 4. Frontend
cd ../web
pnpm install
pnpm dev                                  # http://localhost:3000
```

> Estes comandos são consolidados conforme os componentes são implementados. A fonte canônica de comandos é este README + `CLAUDE.md §9`.
>
> **Auth (W1-C03 → migrada na Sessão 30):** autenticação **própria** — o backend **emite E verifica** o JWT **ES256** próprio (`POST /auth/login` | `/auth/refresh` | `/auth/logout`; cookies **httpOnly**, refresh rotativo persistido em `auth_sessions`, senhas em **argon2id**). Configure o par de chaves EC (`AUTH_JWT_PRIVATE_KEY`/`AUTH_JWT_PUBLIC_KEY`, PEM base64) e o `AUTH_ISSUER`. O frontend fala com o backend por **rewrite same-origin** `/api/:path*` (`BACKEND_INTERNAL_URL`, default `http://127.0.0.1:8000`); a verificação no proxy/SSR usa `jose` com a chave **pública**. O **contrato de claims** (`sub`/`user_id`/`setor`/`administrador`/`aud="authenticated"`) foi preservado **verbatim** — RLS + gates + `access-matrix.ts` intactos. A inatividade de 30 min no app segue complementar. *(As vars `SUPABASE_*` no `.env` estão comentadas — histórico.)* Arquitetura e validação em [`docs/auth.md`](./docs/auth.md).
>
> **Usuários (W1-C04 → migrada na Sessão 30):** a gestão **não depende mais** da Admin API do Supabase. A criação de usuário é **atômica** — credencial (`auth_credentials`, argon2id) **+** linha de domínio (`usuarios`) numa **única transação**; despromoção/desativação **revogam** as sessões ativas. A **política de senha** é validada pela própria API (mínimo 8, letras e dígitos). Primeiro administrador: `uv run python -m src.tasks.bootstrap_admin -- --email <email> --nome "<Nome>" --senha "<Senha>"` (cria credencial + domínio localmente, sem conta prévia). Detalhes em [`docs/usuarios.md`](./docs/usuarios.md) e [`docs/app-shell.md`](./docs/app-shell.md).
>
> **RBAC (W1-C05 · claims na Sessão 30):** `uv run alembic upgrade head` aplica a RLS de `usuarios`. Com a auth própria, os claims `setor`/`administrador` passaram a ser **preenchidos pelo emissor ES256 do backend** (o `custom_access_token_hook` do Supabase ficou **vestigial** — não precisa habilitar nada no dashboard). A Matriz §7 é fonte única (`apps/web/src/lib/access-matrix.ts` + RLS em `apps/api/migrations/rls/`) — toda mudança exige **PR único** cobrindo as duas camadas. Detalhes em [`docs/rbac.md`](./docs/rbac.md).
>
> **Provas (W2-C06):** `uv run alembic upgrade head` cria a tabela **`provas`** (rota imutável via trigger), a **RLS por perfil** e o role de runtime `rastreio_runtime` (migrations `0007`–`0009`; **já aplicadas no Supabase real**, `alembic_version=0009`). O upload da **arte** usa o bucket R2 **`rastreio-provas-artes`** (já existe) e exige as 4 vars **`R2_*`** no ambiente da api (`R2_BUCKET=rastreio-provas-artes` + endpoint/keys via API token do Cloudflare; sem elas a criação responde 503 com erro claro). A **etiqueta PDF** (95×55 mm, QR + código `PRV-AAAA-MM-NNNNNN`) é gerada sob demanda — libs novas da api: `segno`, `fpdf2`, `python-multipart` (entram no `uv sync`). Fluxo local: api de pé → web `/provas/nova` (admin). Em produção, ative o role de runtime não-owner (passo de operação — [`docs/provas.md`](./docs/provas.md) §6).
>
> **Listagem de provas (W2-C07):** `uv run alembic upgrade head` chega à **`0011`** — `0010` adiciona `provas.finalizada_em` (nullable, populada pelo C11) + a função que resolve o nome do vendedor na listagem; `0011` move essa função para o schema **`private`** não exposto pela Data API (remediação dos advisors de RPC). **Já aplicadas no Supabase real** (`alembic_version=0011`). A tela **`/provas`** lista/busca/filtra com escopo por perfil (RLS) e estado de filtros na **URL**; o botão "Ver" leva ao detalhe. Detalhes em [`docs/provas-listagem.md`](./docs/provas-listagem.md).
>
> **Detalhe de provas (W2-C08):** `uv run alembic upgrade head` chega à **`0012`** (`provas.ciclo_atual` NOT NULL default 1 — incrementado pelo C15). A tela **`/provas/[id]`** mostra arte (servida por **proxy** do backend, sem URL pública), metadados, **ciclo atual**, rota/status, ações de etiqueta (**visualizar** em modal / **baixar**) e o **histórico** em empty state (timeline no C13). Página **universal** com escopo pela RLS: acesso fora do escopo **redireciona** sem revelar se a prova existe. A etiqueta deixou de ser admin-only (universal-em-escopo). Detalhes em [`docs/provas-detalhe.md`](./docs/provas-detalhe.md).
>
> **Configurações (W2-C09 — fecha a Wave 2):** `uv run alembic upgrade head` chega à **`0013`** (tabela **`system_settings`** chave-valor + RLS: leitura `authenticated`, escrita admin-only; **já aplicada no Supabase real**, `alembic_version=0013`). A tela **`/configuracoes`** (exclusiva do 3Studio) configura o **tempo de atraso** (horas úteis, padrão 48 — aplicado de imediato, sem cache) e o **template de etiqueta** (padrão/personalizado), com **"Salvar" por card**. O template salvo é respeitado pela geração da etiqueta (C06). Nada novo obrigatório de operação (a tela funciona com os defaults). Detalhes em [`docs/configuracoes.md`](./docs/configuracoes.md).
>
> **Escaneamento (W3-C10 — abre a Wave 3):** `uv run alembic upgrade head` chega à **`0014`** (tabela **`rate_limit_contadores`** + RLS `self` — rate limiting do endpoint de identificação; **já aplicada no Supabase real**, `alembic_version=0014`). A tela **`/escanear`** (mobile-first) identifica a prova por **QR (câmera in-app)** ou **código manual** (formato do C06) — os dois pelo mesmo `POST /provas/identificar`, **idempotente** e **escopado pela RLS**; código inválido/inexistente/fora-de-escopo dão a **mesma** mensagem (anti-enumeração) e há **rate limiting** (30/usuário/min). Câmera negada **não bloqueia** (o manual segue). Ao identificar, vai à tela de **confirmação** (`/provas/[id]/confirmar`) — placeholder onde o C11 (transição) e o C12 (assinatura) plugam. O C10 **só identifica**. Detalhes em [`docs/escaneamento.md`](./docs/escaneamento.md).

> **Máquina de Estados (W3-C11 — o coração do domínio):** `uv run alembic upgrade head` chega à **`0015`** (tabela **`movimentacoes`** append-only = log de auditoria imutável + `acao_enum` + `provas` UPDATE/policies + RLS do Motorista ampliada). A **§6 inteira** (14 estados, 4 rotas) vive em **código** (`apps/api/src/domain/state_machine/`), nunca no banco. **`POST /provas/{id}/transicoes`** executa cada transição de forma **atômica** e **idempotente** (lock pessimista + `idempotency_key` UNIQUE): indefinida → 422, perfil errado → 403 (genérico), fora-de-escopo → 404, chave reusada → 409. Cada transição grava uma linha **imutável** em `movimentacoes`. Cobertura da máquina de estados **100%**. O C11 é o **motor**: quem assina é o **C12**, a timeline é o **C13**, cancelar/reiniciar (e o `ciclo_atual`) são **C14/C15** — todos invocam o motor. Detalhes em [`docs/maquina-estados.md`](./docs/maquina-estados.md).

> **Timeline visual (W3-C13):** `uv run alembic upgrade head` chega à **`0017`** (função **`private.nomes_de_usuarios`** que resolve o nome do responsável de qualquer setor sem ampliar a Matriz §7; **já aplicada no Supabase real**, `alembic_version=0017`). O detalhe (`/provas/[id]`) deixa de mostrar empty state: o componente **`<ProofTimeline>`** lê **`GET /provas/{id}/movimentacoes`** (1 chamada, escopado pela RLS) e desenha o caminho da **rota** (esqueleto **derivado das regras do C11**, sem duplicar a §6), com a etapa **atual destacada** (animada), **laminação** e **travessias de motorista** diferenciadas, **reprovação/cancelamento** com **motivo em destaque** e **múltiplos ciclos** com separador. Animação só `transform`/`opacity`, instantânea sob `prefers-reduced-motion`; a falha do histórico não derruba o detalhe. Detalhes em [`docs/timeline.md`](./docs/timeline.md).
>
> **Cancelamento (W3-C14):** **sem migration nova** (head segue **`0017`**). A ação **"Cancelar prova"** aparece no detalhe (`/provas/[id]`) **só ao 3Studio** e **só em estados ativos**; abre um **modal destrutivo** (motivo obrigatório + aviso de irreversibilidade) que chama **`POST /provas/{id}/cancelar`** — endpoint **dedicado** (gate de borda `cancelar_prova`) que **invoca o motor do C11** (`Acao.CANCELAR` → `cancelada`), gravando a movimentação (ator + data/hora + motivo) no log imutável, **sem assinatura desenhada** (§6.6). **Terminal e irreversível** (RN-005): a prova não reativa; o histórico fica intacto. Acesso em **duas camadas** (borda + motor); perfil não-3Studio → 403. Detalhes em [`docs/cancelamento.md`](./docs/cancelamento.md).
>
> **Reinício de ciclo (W3-C15 — fecha a Wave 3):** `uv run alembic upgrade head` chega à **`0018`** (`GRANT UPDATE (ciclo_atual)` em `provas` a `authenticated` — o Reinício incrementa o contador; **já aplicada no Supabase real**, `alembic_version=0018`). A ação **"Reiniciar ciclo"** aparece no detalhe (`/provas/[id]`) **só ao 3Studio** e **só em "Reprovada pelo Vendedor"**; abre um **modal de confirmação** (**sem motivo**) que chama **`POST /provas/{id}/reiniciar`** — endpoint **dedicado** (gate de borda `reiniciar_ciclo`) que **invoca o motor do C11** (`Acao.REINICIAR_CICLO` → `criada`) e **incrementa `ciclo_atual` na mesma transação atômica**, gravando a movimentação (ator + data/hora) no log imutável, **sem assinatura nem motivo** (§6.6). A **mesma prova** ganha um novo ciclo (mesmo código/QR/etiqueta), **rota e histórico preservados**; a timeline (C13) separa os ciclos. Idempotente (reenvio não reincrementa). Acesso em **duas camadas**; perfil não-3Studio → 403. Detalhes em [`docs/reinicio-ciclo.md`](./docs/reinicio-ciclo.md). **Wave 3 concluída — auditoria sugerida antes da Wave 4.**
>
> **Dashboard (W4-C16 — abre a Wave 4):** `uv run alembic upgrade head` chega à **`0020`** (função de horas úteis **`private.instante_limite_atraso`** do cálculo de "Atrasadas"; **já aplicada no Supabase real**, `alembic_version=0020`). A tela inicial **`/dashboard`** mostra, **fiel ao design** (layout bento), os 5 contadores (**Criadas hoje, Com Vendedor, Aprovadas, Na clicheria, Atrasadas**) **em tempo real** (count-up) e o card **"Atrasadas"** como **lista por vendedor + total**; os números são **escopados por perfil** (RLS) e vêm de **uma única consulta** server-side (sem N+1). Clicar num card abre a **listagem (C07) pré-filtrada**; os atalhos **Escanear** (todos) e **Nova Prova** (só 3Studio) respeitam o perfil. **Operação (opcional, para o push em tempo real):** habilitar a **replicação da tabela `provas`** no painel do Supabase (Database → Replication / publication `supabase_realtime`) — sem isso o painel funciona com a carga SSR (só não recebe atualização automática). Detalhes em [`docs/dashboard.md`](./docs/dashboard.md). **Wave 4 concluída.**

> **Relatórios (W5-C17 — abre a Wave 5):** `uv run alembic upgrade head` chega à **`0021`** (função de horas úteis **`private.horas_uteis_entre`** dos tempos analíticos; **já aplicada no Supabase real**, `alembic_version=0021`). A tela **`/relatorios`** (**exclusiva do 3Studio** — gate de página + endpoints → 403 aos demais) traz **4 abas** (Geral / 3Studio / Vendedores / Clicheria) com uma **barra de filtros compartilhada** (De/Até + presets + Status + busca + rota + Vendedor, estado na URL), **gráficos Recharts** (barras + donut), **tabelas** e **Exportar CSV** (UTF-8 + `;`, Excel pt-BR). As métricas (tempo médio de aprovação, taxa de reprovação, **distribuição por rota somando 100%**, atrasadas — **mesma regra do Dashboard**, devolvidas, tempo médio aguardando da clicheria, etc.) são **agregadas server-side por aba** (lazy, sem N+1), **sem Realtime** (snapshot do período). **Operação:** se `pnpm add` não tiver sido sincronizado, rodar `pnpm install` (o C17 adicionou **`recharts`**). Detalhes em [`docs/relatorios.md`](./docs/relatorios.md).

> **Animações (W6-C19 — abre a Wave 6, frontend-only):** consolida a camada de motion e adiciona **page transitions** (RF-023) + **reveal de entrada ("elementos surgindo em cascata") em todas as telas**. Primitivas em `apps/web/src/components/ui/motion/` (`<PageTransition>`, `<Reveal>`, `<Stagger>`/`<StaggerItem>`) sobre as fábricas de `lib/motion/variants.ts` e os tokens de `lib/motion/tokens.ts`; tudo **GPU-only** (`transform`/`opacity`) e **instantâneo** sob `prefers-reduced-motion` (hook central). Modais/drawer na faixa **150–300 ms** (RF-024). **Sem migration** (não altera o banco). Detalhes em [`docs/animations.md`](./docs/animations.md).
>
> **Log de Auditoria (W6-C20 — fecha a Wave 6 e o backlog v1.0):** `uv run alembic upgrade head` chega à **`0022`** (tabela imutável **`audit_log`** + funções de chain em `private`; **já aplicada no Supabase real**, `alembic_version=0022`). A tela **`/auditoria`** (**exclusiva do 3Studio** — proxy/sidebar + endpoints → 403 aos demais; **read-only**) é um **master-detail** sobre um **log imutável de todas as ações do sistema**: transições, criação e escaneamento, com **Ator/Setor/Prova/Endereço IP/Origem/Data** e um **hash de integridade encadeado** ("Registro íntegro e imutável") verificável. Filtros server-side na URL (presets/Eventos/Ator/Ordem/busca/De-Até/Linhas), color-coding por tipo, scroll infinito, drill-in no mobile. A captura é **efeito colateral atômico** dos casos de uso (não muda a regra deles); a escrita só ocorre pela função `private.audit_log_append` (anti-forja). **Pendências adiadas:** eventos periféricos (login/config) e endurecimento HMAC do chain. Detalhes em [`docs/auditoria.md`](./docs/auditoria.md). **Backlog v1.0 COMPLETO.**

---

## Testes

```bash
# Backend
cd apps/api
uv run pytest --cov                       # unitários + integração (suíte roda offline;
                                          #   testes @db pulam sem Postgres local)
uv run ruff check . && uv run mypy        # lint + tipos (strict)
uv run python -m src.tasks.keep_alive     # keep-alive: ping read-only ao banco (W0-C02)
                                          #   ver docs/keep-alive.md p/ ligar em produção

# Frontend
cd apps/web
pnpm lint && pnpm build                   # lint + type-check (build)
pnpm test                                 # vitest (componentes/lógica — RTL/jsdom)
pnpm test:e2e                             # Playwright E2E (telas, responsivo, erro genérico)
```

**Metas de cobertura:** ≥ 80% em domínio/serviço · **≥ 95% na máquina de estados** · 100% dos endpoints críticos na integração.

---

## Banco de dados e migrations

- **Tabelas de domínio** → gerenciadas **exclusivamente** por Alembic (`apps/api/migrations/`).
- **Tabelas de Auth** (`auth_credentials`, `auth_sessions`) → **agora locais e versionadas por Alembic** (migration `0023`, Sessão 30). As funções `private.auth_*` (SECURITY DEFINER) ficam no mesmo lote. *(O schema `auth.*` do Supabase deixou de existir neste projeto.)*
- **Políticas RLS** → versionadas em `apps/api/migrations/rls/`. **Reaplicar após qualquer recriação de tabela.**
- **Enums de domínio** → criados via `CREATE TYPE` em migrations; alterações via `ALTER TYPE ... ADD VALUE`.

Regra crítica e separação completa de responsabilidades: ver DAT §2 e `CLAUDE.md §11`.

---

## Roadmap (waves)

| Wave | Componentes | Status |
| --- | --- | --- |
| **0 · Infra** | 01 Infraestrutura ✅ · 02 Keep-Alive ✅ | **Concluída** ✅ |
| **1 · Auth/RBAC** | 03 Login ✅ · 04 Usuários (+ app shell) ✅ · 05 Matriz RBAC ✅ | **Concluída** ✅ |
| **2 · Núcleo** | 06 Cadastro+Rota+Etiqueta ✅ · 07 Listagem ✅ · 08 Detalhe ✅ · 09 Configurações ✅ | **Concluída** ✅ |
| **3 · Fluxo** | 10 Escaneamento ✅ · 11 Máquina de Estados ✅ · 12 Assinatura ✅ · 13 Timeline ✅ · 14 Cancelamento ✅ · 15 Reinício ✅ | **Concluída** ✅ |
| **4 · Dashboard** | 16 Dashboard Realtime ✅ | **Concluída** ✅ |
| **5 · Relatórios/UX** | 17 Relatórios ✅ · ~~18 Atalhos~~ ✗ descartado (ADR-095) | 🔄 re-auditoria pendente |
| **6 · Animações/Auditoria** | 19 Animações ✅ · 20 Log de Auditoria ✅ | **Concluída** ✅ |

> **Backlog v1.0 COMPLETO.** Próximo passo: auditoria de fechamento da Wave 6 / revisão final de sistema (e a re-auditoria pendente da Wave 5).

> Cada wave só inicia após concluir as dependências da anterior. **Uma sessão = um componente completo.**

---

## Como contribuir

- **Branches (gitflow leve, ADR-016):** `main` = estável · `develop` = integração (**padrão**). O trabalho dos componentes segue em `develop` (ou branches de feature); PRs apontam para `develop`. Repositório: [`3studioagn/Sistema-Digital`](https://github.com/3studioagn/Sistema-Digital).
- Commits em **Conventional Commits**, com escopo de componente: `feat(w0-c01): ...`.
- Toda alteração na **Matriz de Acesso** exige **PR único** cobrindo `access-matrix.ts` **e** as migrations de RLS.
- PR que sincroniza enums deve tocar **os dois lados** (Python e PostgreSQL).
- Ao final de cada sessão, executar o **Protocolo de Encerramento** (`CLAUDE.md §10`).

---

*3Studio · Documentação viva. Mantenha este README verdadeiro a cada entrega.*
