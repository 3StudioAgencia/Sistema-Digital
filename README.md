# Rastreio de Provas Digitais

Plataforma web da **3Studio** para controle e rastreabilidade do fluxo físico-digital de provas de impressão — da criação à conclusão na clicheria — com máquina de estados de **14 estados** em **4 rotas**, RBAC em duas camadas e identificação por QR Code (câmera) com fallback de digitação manual.

- **Versão (baseline):** v1.0 — Junho/2026
- **Custo-alvo:** R$ 0 (free tier Supabase + Cloudflare R2)
- **Documentação de contexto:** [`CLAUDE.md`](./CLAUDE.md) · [`DECISIONS.md`](./DECISIONS.md) · [`CHANGELOG.md`](./CHANGELOG.md) · [`SESSION_LOG.md`](./SESSION_LOG.md)

---

## Stack

| Camada | Tecnologias |
| --- | --- |
| **Frontend** | Next.js (App Router, ≥14) · TypeScript (strict) · CSS Modules · Framer Motion · Recharts · html5-qrcode · qrcode.react · react-signature-canvas |
| **Backend** | Python 3.12 · FastAPI (async) · SQLAlchemy 2.0 async · Pydantic v2 · Alembic · PyJWT (só verifica) |
| **Banco / Auth / Realtime** | PostgreSQL (Supabase) · Supabase Auth · Supabase Realtime · Row Level Security |
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
- **Docker** (Postgres local para dev/testes — opcional: a suíte roda offline sem ele)
- Contas: **Supabase** (projeto) e **Cloudflare R2** (bucket) — provisionamento em [`docs/setup-infra.md`](./docs/setup-infra.md)

> **Plataformas de deploy confirmadas:** **Vercel** (web) + **Railway** (API), on-prem futuro revisável (ADR-009, *Aceita*); gerenciadores de pacote `uv`/`pnpm` confirmados (ADR-010). Ver `DECISIONS.md`.

---

## Setup local

```bash
# 1. Variáveis de ambiente (preencher a partir dos exemplos)
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env

# 2. Postgres local (dev/testes)
docker compose up -d db

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
> **Auth (W1-C03):** preencha `SUPABASE_URL` (api) e a *publishable key* em `NEXT_PUBLIC_SUPABASE_ANON_KEY` (web). O backend **verifica** o JWT do Supabase (**ES256 via JWKS + HS256 fallback**; prova em `GET /auth/me`) — nunca emite. Arquitetura, fluxo e validação local em [`docs/auth.md`](./docs/auth.md). Ajuste o **TTL do access token** no dashboard do Supabase (a inatividade de 30 min no app é complementar).
>
> **Usuários (W1-C04):** a gestão de usuários exige a chave secreta da Admin API no backend — **`SUPABASE_SECRET_KEY`** (Dashboard → Project Settings → API Keys → *Secret keys*; **server-only**, jamais no frontend). Sem ela a app sobe e a gestão responde 503. Configure também a **política de senha** no dashboard (Authentication → Providers → Password: mínimo 8, letras e dígitos — a API valida o mesmo). Primeiro administrador: `uv run python -m src.tasks.bootstrap_admin -- --email <email> --nome "<Nome>"` (a conta precisa existir no Supabase Auth). Detalhes em [`docs/usuarios.md`](./docs/usuarios.md) e [`docs/app-shell.md`](./docs/app-shell.md).
>
> **RBAC (W1-C05):** rode `uv run alembic upgrade head` (cria o **Custom Access Token Hook** e a RLS de `usuarios`) e **habilite o hook** no dashboard: Authentication → Hooks → *Customize Access Token (JWT) Claims* → `public.custom_access_token_hook`. Sem isso o JWT não carrega `setor`/`administrador` no topo e a RLS/proxy tratam todos como menor privilégio. A Matriz §7 é fonte única (`apps/web/src/lib/access-matrix.ts` + RLS em `apps/api/migrations/rls/`) — toda mudança exige **PR único** cobrindo as duas camadas. Detalhes em [`docs/rbac.md`](./docs/rbac.md).
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
- **Tabelas de Auth** (`auth.*`) → gerenciadas pelo Supabase. **Não tocar via Alembic.**
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
| **3 · Fluxo** | 10 Escaneamento ✅ · 11 Máquina de Estados ✅ · 12 Assinatura · 13 Timeline · 14 Cancelamento · 15 Reinício | **Em andamento** 🚧 |
| **4 · Dashboard** | 16 Dashboard Realtime | ⬜ |
| **5 · Relatórios/UX** | 17 Relatórios · 18 Atalhos | ⬜ |
| **6 · Animações/Auditoria** | 19 Animações · 20 Log de Auditoria | ⬜ |

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
