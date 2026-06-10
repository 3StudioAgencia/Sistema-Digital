# Setup de Infraestrutura — Provisionamento real (W0-C01)

Guia passo-a-passo para provisionar **Supabase** (Postgres/Auth/Realtime) e
**Cloudflare R2** (storage de artes), preencher os `.env` e validar a fundação.
**Custo-alvo: R$ 0** — tudo dentro do free tier.

> O repositório roda e é testável **sem** credenciais reais (Postgres local via
> docker-compose + storage mockado). Este guia é para quando staging/produção
> forem ligados.

---

## 1. Supabase (banco gerenciado + Auth + Realtime)

> **✅ JÁ PROVISIONADO (2026-06-09):** projeto **`rastreio-provas-digitais`**
> — ref `wmpxxrzbzqgsorjwczvz` · região `sa-east-1` (São Paulo) · PostgreSQL 17 ·
> URL `https://wmpxxrzbzqgsorjwczvz.supabase.co` · `pgcrypto` já instalado.
> Os passos abaixo ficam como referência para recriação em outro ambiente.

1. Crie uma conta/organização em [supabase.com](https://supabase.com) e clique
   em **New project** (plano **Free**).
   - Nome: `rastreio-provas-digitais` · Região: `South America (São Paulo)`.
   - Guarde a **senha do banco** num cofre (não será exibida de novo).
2. Obtenha as **duas connection strings** (ADR-007) em
   **Project Settings → Database → Connection string**:
   - **Runtime (pooler de transação, porta 6543)** — seletor "Transaction":
     `postgresql://postgres.<ref>:<senha>@aws-0-sa-east-1.pooler.supabase.com:6543/postgres`
     → vai em `DATABASE_URL` da API.
   - **Migrations (conexão direta, porta 5432)** — seletor "Direct connection":
     `postgresql://postgres:<senha>@db.<ref>.supabase.co:5432/postgres`
     → vai em `MIGRATIONS_DATABASE_URL` da API.
3. Em **Project Settings → API**, copie:
   - **Project URL** → `SUPABASE_URL` (api) e `NEXT_PUBLIC_SUPABASE_URL` (web);
   - **anon/publishable key** → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (web);
   - **JWT Secret** → `SUPABASE_JWT_SECRET` (api — usado a partir da Wave 1;
     PyJWT **só verifica** tokens, nunca emite).
4. **Atenção (free tier):** o projeto é **pausado após ~7 dias sem requisições**.
   O Componente **W0-C02 (Cron Keep-Alive)** mitiga isso — deve entrar junto
   com o primeiro deploy.

## 2. Cloudflare R2 (storage S3-compatível, egress zero)

> **✅ BUCKET JÁ CRIADO (2026-06-09):** **`rastreio-provas-digitais`**
> (storage class Standard). Falta apenas o **API Token** (passo 3) e o
> **endpoint da conta** (passo 4) para preencher o `.env` da API.

1. Crie uma conta em [dash.cloudflare.com](https://dash.cloudflare.com) e ative
   o **R2** (plano free: 10 GB; pede cartão, sem cobrança dentro do limite).
2. **R2 → Create bucket**: nome `rastreio-provas-digitais` (região automática).
3. **R2 → Manage R2 API Tokens → Create API Token**:
   - Permissão **Object Read & Write**, escopo restrito ao bucket
     `rastreio-provas-digitais`.
   - Copie `Access Key ID` → `R2_ACCESS_KEY_ID` e
     `Secret Access Key` → `R2_SECRET_ACCESS_KEY`.
4. O endpoint da conta é `https://<account_id>.r2.cloudflarestorage.com`
   (exibido na página do R2) → `R2_ENDPOINT_URL`;
   `R2_BUCKET=rastreio-provas-digitais`.
5. **Regra tudo-ou-nada:** preencha as 4 variáveis `R2_*` ou nenhuma — config
   parcial falha no boot, de propósito (erro de operação detectado cedo).

## 3. Preencher os `.env`

```bash
cp apps/api/.env.example apps/api/.env     # preencher com os valores acima
cp apps/web/.env.example apps/web/.env
```

Em **dev local sem contas**, mantenha as URLs do Postgres do docker-compose e
deixe `R2_*`/`SUPABASE_*` vazios — a API sobe e o readiness reporta o que falta.

## 4. Migrations e subida local

```bash
docker compose up -d db                    # Postgres 17 local (dev/teste)
cd apps/api
uv sync
uv run alembic upgrade head                # baseline (pgcrypto) — usa MIGRATIONS_DATABASE_URL
uv run uvicorn src.main:app --reload       # http://localhost:8000/docs

cd ../web
pnpm install && pnpm dev                   # http://localhost:3000 (página de status)
```

Contra o **Supabase real**: o mesmo `alembic upgrade head` com
`MIGRATIONS_DATABASE_URL` apontando para a conexão direta (5432). A extensão
`pgcrypto` já existe no Supabase — a baseline é idempotente (`IF NOT EXISTS`).

## 5. Validar o storage R2 real (quando houver credenciais)

A suíte cobre o storage com `moto` (offline). Para validar contra o R2 real:

```bash
cd apps/api
uv run python - <<'EOF'
from src.adapters.outbound.storage.r2_storage import R2Storage
from src.infrastructure.config import get_settings

storage = R2Storage.from_settings(get_settings())
key = storage.upload("healthcheck/teste.txt", b"ola r2", "text/plain")
assert storage.download(key) == b"ola r2"
storage.delete(key)
print("R2 OK: upload/download/delete via porta")
EOF
```

## 6. Deploy (ADR-009 — plataformas a confirmar)

- **Web → Vercel** (free): importe o repo, root `apps/web`, defina as
  `NEXT_PUBLIC_*` no painel. O CI já valida lint+build em todo PR.
- **API → host de containers** (Fly.io/Render, free): a imagem é
  `apps/api/Dockerfile` (multi-stage, non-root, healthcheck embutido).
  O passo de release DEVE rodar `alembic upgrade head` antes de trocar tráfego.
- Segredos **somente** nos cofres das plataformas/GitHub Secrets — nunca no repo.
- Monitoramento (RNF-024): aponte o uptime monitor para `GET /health` e
  `GET /health/ready` do staging (ex.: UptimeRobot free, intervalo 5 min).

## 7. Checklist de verificação (critérios de aceitação do C01)

- [ ] `uv run alembic upgrade head` aplica em banco limpo; `downgrade base` desfaz;
      novo `upgrade head` reaplica (repetível).
- [ ] Upload + leitura de arquivo de teste via porta de storage:
      automatizado com moto (`tests/unit/test_storage.py`) e manual contra o
      R2 real (§5 acima).
- [ ] `GET /health` → `200 {"status":"ok"}` com header `X-Request-ID`.
- [ ] `GET /health/ready` → `200` com tudo ok; `503` com `checks` detalhando a
      dependência fora (`database`/`storage`).
- [ ] Nenhum segredo versionado; `.env.example` cobre todas as chaves.
- [ ] Free tier em tudo (Supabase free + R2 free + hosts free).
