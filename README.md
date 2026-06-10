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
- **Docker** (Postgres local para dev/testes)
- Contas: **Supabase** (projeto) e **Cloudflare R2** (bucket)

> A definição final de gerenciadores de pacote e plataformas de deploy é revisável — ver `DECISIONS.md` ADR-009/ADR-010.

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

---

## Testes

```bash
# Backend
cd apps/api
uv run pytest --cov                       # unitários + integração (cobertura)
uv run ruff check . && uv run mypy src    # lint + tipos

# E2E (após as telas existirem)
pnpm exec playwright test
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
| **0 · Infra** | 01 Infraestrutura · 02 Keep-Alive | ⏳ Em andamento |
| **1 · Auth/RBAC** | 03 Login · 04 Usuários · 05 Matriz RBAC | ⬜ |
| **2 · Núcleo** | 06 Cadastro+Rota+Etiqueta · 07 Listagem · 08 Detalhe · 09 Config | ⬜ |
| **3 · Fluxo** | 10 Escaneamento · 11 Máquina de Estados · 12 Assinatura · 13 Timeline · 14 Cancelamento · 15 Reinício | ⬜ |
| **4 · Dashboard** | 16 Dashboard Realtime | ⬜ |
| **5 · Relatórios/UX** | 17 Relatórios · 18 Atalhos | ⬜ |
| **6 · Animações/Auditoria** | 19 Animações · 20 Log de Auditoria | ⬜ |

> Cada wave só inicia após concluir as dependências da anterior. **Uma sessão = um componente completo.**

---

## Como contribuir

- Commits em **Conventional Commits**, com escopo de componente: `feat(w0-c01): ...`.
- Toda alteração na **Matriz de Acesso** exige **PR único** cobrindo `access-matrix.ts` **e** as migrations de RLS.
- PR que sincroniza enums deve tocar **os dois lados** (Python e PostgreSQL).
- Ao final de cada sessão, executar o **Protocolo de Encerramento** (`CLAUDE.md §10`).

---

*3Studio · Documentação viva. Mantenha este README verdadeiro a cada entrega.*
