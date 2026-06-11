# Keep-Alive do Postgres (Supabase) — W0-C02

Rotina agendada que impede a **pausa automática** do projeto Supabase no free
tier, mantendo o banco disponível e "quente" no horário comercial (**RNF-011**),
ao **mínimo de requisições necessário** (**RNF-023**) e com **alerta de falha**
(**RNF-024**). **Custo: R$ 0.**

> **TL;DR para ligar em produção:** cadastre o secret `KEEPALIVE_DATABASE_URL`
> no repositório (Settings → Secrets and variables → Actions) com a connection
> string da **conexão direta/sessão (5432)** do Supabase. O workflow
> [`.github/workflows/keep-alive.yml`](../.github/workflows/keep-alive.yml) passa
> a rodar **uma vez por dia** às 06:00 (America/Sao_Paulo). Opcionalmente,
> cadastre `ALERT_WEBHOOK_URL` para receber alerta de falha.

---

## 1. Por que isto existe

O **free tier do Supabase pausa o projeto após 7 dias sem requisições.** Um
projeto pausado derruba o banco inteiro — e, com ele, toda a aplicação. Basta um
feriado prolongado ou uma semana de baixo uso para o sistema "sumir".

A defesa é trivial em código e crítica em consequência: **qualquer requisição
real ao banco reinicia o contador de inatividade.** Esta rotina faz exatamente
uma — um `SELECT now()` read-only — em cadência segura.

---

## 2. Por que o gatilho é EXTERNO ao Supabase e à API (ADR-015)

Duas alternativas tentadoras estão **erradas** para este fim:

| Alternativa | Por que NÃO serve |
| --- | --- |
| **`pg_cron`** (cron interno do Postgres) | Se o projeto Supabase pausar, o `pg_cron` pausa **junto** e não consegue se auto-acordar. O keep-alive precisa vir **de fora**. |
| **Scheduler embutido na API** (APScheduler, etc.) | Se o host da API hibernar (free tier), o scheduler hiberna **junto**. |

**Decisão (ADR-015):** o keep-alive é um **scheduler externo e independente do
host da API**, que invoca uma **rotina read-only de _ping_** ao banco. A lógica
de ping mora em código testável e reutilizável; o scheduler é só o gatilho
(portanto trocável).

- **Scheduler primário:** **GitHub Actions scheduled workflow**. Custo zero, já
  existe o repositório/CI, totalmente desacoplado do host da API, histórico de
  execuções como trilha de auditoria e **notificação nativa de falha**.

---

## 3. Como funciona

```
GitHub Actions (cron diário)
        │  uv run python -m src.tasks.keep_alive   (em apps/api)
        ▼
src/tasks/keep_alive.py
        │  conexão DIRETA/sessão (5432, MIGRATIONS_DATABASE_URL), one-shot
        ▼
src/infrastructure/database.py :: fetch_db_time(engine)   ← MESMA função do readiness
        │  SELECT now()  (read-only, sem efeito colateral)
        ▼
Postgres do Supabase  → reinicia o contador de inatividade de 7 dias
```

- **Reuso (DRY):** a ida ao banco é a **mesma** usada pelo health check
  `/health/ready` do C01. Há **uma única** função com a lógica de conexão —
  `fetch_db_time()` —, consumida tanto pelo `ping()` do readiness quanto pelo
  keep-alive. Sem duplicação de lógica de banco.
- **Conexão direta (5432), não o pooler (6543):** para um único `SELECT`
  *one-shot* a conexão direta/sessão evita qualquer peculiaridade do pooler de
  transação. Reutiliza `MIGRATIONS_DATABASE_URL` (a mesma URL das migrations —
  ADR-007).
- **Observabilidade:** cada execução emite **uma linha JSON estruturada** em
  stdout, capturada pelo log do run do GitHub Actions.

### Exemplo de log — sucesso (`exit 0`)
```json
{"timestamp":"2026-06-11T11:47:17.948Z","level":"INFO","logger":"rastreio.keep_alive",
 "message":"keep-alive ok","event":"keep_alive","status":"ok","latency_ms":331.42,
 "db_time":"2026-06-11T11:47:17.948934+00:00","correlation_id":"56f6…38a","env":"production"}
```

### Exemplo de log — falha (`exit 1`)
```json
{"timestamp":"2026-06-11T11:47:06.489Z","level":"ERROR","logger":"rastreio.keep_alive",
 "message":"keep-alive falhou","event":"keep_alive","status":"error",
 "correlation_id":"dbd1…435","env":"production","error_type":"ConnectionRefusedError"}
```

> **Segredos nunca vazam no log:** em falha registra-se apenas o **tipo** da
> exceção (`error_type`), nunca `str(exc)` — a mensagem do driver pode conter a
> connection string. Há teste automatizado provando que a senha não aparece em
> stdout.

---

## 4. Cadência e seu racional (RNF-023 + RNF-011)

- **Restrição dura:** o intervalo entre execuções é **sempre << 7 dias**.
- **Padrão:** **uma execução diária**, às **06:00 America/Sao_Paulo** =
  **`0 9 * * *` (UTC)** — uma hora antes do horário comercial (07:00), deixando
  o banco "quente" para o dia útil.
  - O Brasil **não tem horário de verão desde 2019**: BRT = UTC−3 o ano todo,
    sem complicação de DST. Por isso o cron fixo em UTC é seguro.
- **Por que diário (e não de hora em hora):** diário dá **~7× de margem** sobre
  o limite de 7 dias — robusto contra atrasos/saltos do GitHub cron — e atende
  ao RNF-011 **sem polling excessivo**. Frequências sub-horárias violariam o
  RNF-023 (mínimo de requisições) sem ganho real.
- **Configurável pela expressão cron.** Rodar **só em dias úteis** também é
  aceitável (o gap máximo de fim de semana continua < 7 dias):
  ```yaml
  - cron: "0 9 * * 1-5"
  ```

---

## 5. Alerta de falha (RNF-024)

Em camadas, do baseline ao opcional:

1. **Exit code ≠ 0** → o passo do workflow falha → **o run inteiro fica
   vermelho** → **notificação nativa do GitHub** (e-mail/UI) ao(s)
   responsável(eis). Suficiente como baseline, sem configurar nada.
2. **Webhook opcional:** se o secret `ALERT_WEBHOOK_URL` existir, um passo
   `if: failure()` posta uma mensagem curta (Slack/Discord/genérico) com o link
   do run. **Sem o secret, o passo é simplesmente pulado** — nada hardcoded.
   - Payload enviado (estilo Slack): `{"text": "… Run: <url>"}`. Para Discord,
     ajuste o campo para `content` no workflow (Discord ignora `text`).

---

## 6. Ligar em produção — passo a passo

1. **Secret obrigatório.** Repositório → **Settings → Secrets and variables →
   Actions → New repository secret**:
   - **Nome:** `KEEPALIVE_DATABASE_URL`
   - **Valor:** a connection string da **conexão direta/sessão (porta 5432)** do
     Supabase — a **mesma** usada em `MIGRATIONS_DATABASE_URL`
     (ver [`setup-infra.md`](./setup-infra.md) §1). O prefixo `postgres://` /
     `postgresql://` é normalizado automaticamente para `postgresql+asyncpg://`.
     - ⚠️ Na rede de dev a conexão **direta** `db.<ref>.supabase.co:5432` é
       **IPv6-only**; os runners do GitHub Actions têm IPv6, mas o **pooler em
       modo session** (`postgres.<ref>@aws-1-<região>.pooler.supabase.com:5432`)
       é a opção mais portável e suporta o `SELECT` one-shot (ADR-007, emenda).
2. **Secret opcional (alerta):** `ALERT_WEBHOOK_URL` com a URL do webhook.
3. **Habilitar o workflow.** Workflows agendados do GitHub executam a versão do
   arquivo na **branch padrão** do repositório — aqui **`develop`** (ADR-016),
   **não** `main`. Alterações de cadência (cron) só têm efeito quando feitas na
   branch padrão. Confirme o estado em **Actions → Keep-Alive (Supabase)**.
4. **Validar manualmente** (não esperar até as 06:00): **Actions → Keep-Alive
   (Supabase) → Run workflow** (`workflow_dispatch`). Veja o log JSON
   `status="ok"` e o run verde.

> O workflow define `DATABASE_URL` **e** `MIGRATIONS_DATABASE_URL` a partir do
> mesmo secret. A rotina só usa a segunda; a primeira existe porque o `Settings`
> do C01 a exige no boot — apontá-la para o mesmo valor é inócuo e evita um
> segundo secret.

---

## 7. Testar/rodar localmente

```bash
cd apps/api

# Sucesso (Postgres local do docker-compose OU Supabase real via .env):
uv run python -m src.tasks.keep_alive          # → log status="ok", exit 0

# Falha controlada (credencial inválida) — demonstra exit≠0 + log de erro:
MIGRATIONS_DATABASE_URL="postgresql+asyncpg://x:y@127.0.0.1:9/nada" \
DATABASE_URL="postgresql+asyncpg://x:y@127.0.0.1:9/nada" \
  uv run python -m src.tasks.keep_alive        # → log status="error", exit 1
```

Testes automatizados:
- `tests/unit/test_keep_alive.py` — offline: contrato dos campos do log,
  exit codes e **não-vazamento de credencial**.
- `tests/integration/test_keep_alive.py` — `@db`: sucesso ponta a ponta contra
  Postgres real (skip sem banco local; obrigatório no CI).

---

## 8. Hardening de longo prazo — alternativa Cloudflare Worker Cron (apenas documentado)

O GitHub **desabilita workflows agendados após 60 dias de inatividade do
repositório** e pode atrasar/saltar execuções sob carga. A cadência diária
(~7× de margem) absorve atrasos pontuais, mas para um horizonte longo o mais
robusto é um **Cloudflare Worker com Cron Trigger**:

- **Mesmo ecossistema do R2** já usado pelo projeto (uma conta a menos a manter).
- **Sem o limite de 60 dias** do GitHub Actions.
- Custo zero no free tier dos Workers.
- Esboço (NÃO implementar agora): um Worker com
  `crons = ["0 9 * * *"]` no `wrangler.toml` cujo handler `scheduled` faz uma
  requisição HTTPS ao endpoint `/health/ready` da API **ou** um `SELECT` via
  driver Postgres do Worker. A lógica de ping permanece a mesma; muda só o
  gatilho — exatamente o que o ADR-015 prevê ao manter o scheduler trocável.

Decisão registrada em [`DECISIONS.md`](../DECISIONS.md) (ADR-015).
