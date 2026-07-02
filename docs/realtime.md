# Realtime do Dashboard — SSE + Postgres `LISTEN/NOTIFY` (Etapa 3 da migração)

> Substitui o **Realtime do Supabase** (neutralizado na ADR-113) por um mecanismo
> **próprio, sem serviço externo, custo R$ 0**. Fecha a migração Supabase → local.
> Decisões: **ADR-114** (design) + **ADR-115..118** (implementação). Escopo: **só o
> dashboard**.

## 1. O que é (e o que NÃO é)

O dashboard (C16) precisa **reagir ao vivo** a mudanças de prova (criação, transição,
cancelamento, reinício). O mecanismo:

- **Transporte:** **SSE** (Server-Sent Events) — canal de **mão única
  servidor→navegador**. Basta para o dashboard, que só precisa *receber* o aviso
  "algo mudou". WebSocket ficou **reservado** para uma futura necessidade de mão
  dupla (não existe hoje).
- **Fan-out entre processos:** **Postgres `LISTEN/NOTIFY`** — sem Redis, sem
  serviço novo. Resolve o broadcast num backend **stateless / escala horizontal**
  (cada processo mantém o SEU `LISTEN`; todos recebem o `NOTIFY`).
- **Evento GENÉRICO:** o canal transporta só o sinal `"mudou"` — **nunca** números
  por perfil. O navegador, ao receber, **rebusca `GET /dashboard`**, que já vem
  **escopado pela RLS**. É o que preserva a Matriz §7 (`NOTIFY`/`LISTEN` NÃO sofrem
  RLS — um payload com dado de domínio vazaria entre perfis).
- **Sem polling** (RNF-021): o push é event-driven. O debounce colapsa rajadas.

```
POST /provas/{id}/transicoes ─┐   (mesma transação, só no commit)
POST /provas (criação)        ├─► pg_notify('eventos_provas','mudou')
POST .../cancelar|reiniciar  ─┘
                                        │  (Postgres entrega no COMMIT)
        ┌───────────────────────────────┴───────────────────────────────┐
        ▼ (cada processo do backend tem 1 LISTEN)                         ▼
   PgEventListener ──► EventoHub.broadcast() ──► filas dos streams SSE abertos
                                                        │
   navegador (EventSource /api/dashboard/stream) ◄──────┘  "data: mudou"
        │
        └─► refetch debounced de GET /dashboard  (escopado pela RLS) ─► count-up
```

## 2. Backend (Ports & Adapters)

| Peça | Arquivo | Papel |
| --- | --- | --- |
| Constantes do canal/payload | `apps/api/src/domain/eventos.py` | `CANAL_EVENTOS_PROVAS="eventos_provas"`, `EVENTO_PROVA_MUDOU="mudou"` (fonte única). |
| Porta | `apps/api/src/application/ports/event_bus.py` | `EventBusPort.publicar_mudanca_de_prova()` — molde do `AuditLogPort`. |
| Adapter (publisher) | `apps/api/src/adapters/outbound/db/event_bus_pg.py` | `PgNotifyEventBus(session)` → `SELECT pg_notify(...)` na MESMA sessão/transação. |
| Hub + Listener | `apps/api/src/infrastructure/realtime.py` | `EventoHub` (fan-out in-process) + `PgEventListener` (LISTEN resiliente). |
| Endpoint SSE | `apps/api/src/adapters/inbound/http/dashboard.py` | `GET /dashboard/stream` (`StreamingResponse`). |
| Gate curto | `apps/api/src/adapters/inbound/http/dependencies.py` | `autorizar_stream_dashboard` (sessão RLS **curta**). |
| Wiring | `apps/api/src/main.py` | hub em `app.state`; listener sobe/encerra no `lifespan`. |
| Helper de DSN | `apps/api/src/infrastructure/config.py` | `to_asyncpg_dsn` (`+asyncpg://`→`postgresql://` p/ o asyncpg cru). |

### 2.1 Emissão atômica (ADR-115)

O `pg_notify` é executado pela **mesma `AsyncSession`** do caso de uso, então entra
na transação corrente e o Postgres **só o entrega no COMMIT** (descarta em
rollback). É emitido **apenas no ramo de mudança NOVA** — nunca no reenvio
idempotente (`transicoes.py`: dentro do `else`, junto do `AuditLogPort.registrar`,
antes do `commit`; `provas.py`: no `_inserir_com_retry`, junto do audit). Assim o
sinal é **atômico** (RNF-017) e **idempotente** (RNF-015): reenvio não re-sinaliza
(evita refetch à toa em todos os navegadores — *thundering herd*).

### 2.2 Endpoint SSE (ADR-116)

`GET /dashboard/stream`:
- **Auth pelo cookie** `access_token` (via `get_current_user`, cookie-primeiro) — o
  `EventSource` não manda header custom, então o cookie same-origin é o único
  caminho. Gate `Recurso.DASHBOARD` (universal) numa **sessão RLS curta** (abre,
  autoriza, **fecha**) — o stream **não** segura conexão de banco (`NullPool`).
- **`StreamingResponse` puro** (`text/event-stream`) — sem `sse-starlette` (dep
  mínima). Headers `Cache-Control: no-store` + **`X-Accel-Buffering: no`**.
- **Heartbeat** (`: ping`, ~20 s) para não cair por idle timeout de proxy.
- **TTL de conexão** derivado do `exp` do token: o servidor fecha o stream ~60 s
  **antes** de o access token (30 min) expirar, emitindo o evento **`expira`** — o
  cliente renova o cookie e reabre (o `EventSource` não faz refresh sozinho).
- Limpa a inscrição no `finally` (sem filas órfãs), mesmo em disconnect abrupto.

### 2.3 Hub + Listener (ADR-117)

- **`EventoHub`** — filas **bounded** (`maxsize=8`); `broadcast()` faz `put_nowait`
  e **descarta** em fila cheia (nunca bloqueia o fan-out nem espera um cliente
  lento). Perder um sinal intermediário é inócuo (payload genérico → o próximo
  refetch reconcilia).
- **`PgEventListener`** — **uma** conexão asyncpg dedicada em `LISTEN`, em conexão
  **direta/sessão** (derivada de `MIGRATIONS_DATABASE_URL`; `LISTEN` **não**
  sobrevive a um pooler em modo transação). Resiliente: reconecta com backoff e
  re-`LISTEN`, e emite um sinal de "rebusca" ao (re)conectar (fecha a janela em que
  `NOTIFY` possa ter sido perdido — o Postgres não persiste notificações). **Um por
  processo**; escala de graça (o bus é o Postgres).

## 3. Frontend

| Peça | Arquivo | Papel |
| --- | --- | --- |
| Helper do stream | `apps/web/src/lib/api/eventos.ts` | `assinarDashboard({onMudou,onExpira})` → `EventSource("/api/dashboard/stream",{withCredentials:true})`; devolve cleanup. |
| Gancho | `apps/web/src/app/(app)/dashboard/_components/dashboard-view.tsx` | `useEffect` que assina, faz refetch com **debounce ~800 ms + jitter**, trata `expira` (→ `POST /api/auth/refresh` → reabre) e limpa no unmount. |

- **Same-origin obrigatório:** o `EventSource` vai por `/api/*` (rewrite do
  `next.config`), então o cookie httpOnly flui automático — não apontar cross-origin
  ao backend (CORS + `SameSite=lax` bloqueariam).
- **Count-up:** o `<AnimatedCounter>` reage sozinho às mudanças de estado — o refetch
  só chama `setDados`.
- **Degradação graciosa:** queda do stream mantém o último valor; o `EventSource`
  reabre (ou, num 4xx fatal, fica no último valor até uma navegação/refetch manual).

## 4. Deploy on-prem — contrato do reverse proxy (ADR-118) ⚠️

A app roda **on-prem** (frontend + API + Postgres juntos, atrás de um reverse
proxy). Para o SSE funcionar, o proxy (ex. nginx) **precisa** ser configurado na
rota do stream (`/api/dashboard/stream` → backend):

- **Desligar o buffering de resposta** (SSE precisa de resposta *chunked* sem
  buffer). Em nginx: `proxy_buffering off;` — o backend já envia
  `X-Accel-Buffering: no`, que o nginx respeita.
- **Não comprimir** `text/event-stream` (gzip bufferiza) — ex.: excluir esse
  content-type do `gzip_types`.
- **`proxy_read_timeout` > intervalo de heartbeat** (o backend faz ping a cada
  ~20 s) — ex.: `proxy_read_timeout 90s;`. Senão o proxy derruba o stream ocioso.
- **HTTP/2 recomendado** no proxy (elimina o limite de ~6 conexões por origem do
  HTTP/1.1 se o dashboard for aberto em várias abas).
- O `PgEventListener` exige **conexão direta de sessão** ao Postgres
  (`MIGRATIONS_DATABASE_URL`) — nunca um pooler em modo transação.

## 5. Migrations / RLS

**Nenhuma.** `LISTEN`/`NOTIFY`/`pg_notify` não exigem schema, GRANT, RLS nem enum. O
head do Alembic permanece `0023`.

## 6. Testes

- **Unit (offline):** `tests/unit/test_realtime.py` (`EventoHub`, `to_asyncpg_dsn`);
  `tests/unit/test_dashboard_stream.py` (gerador SSE: conectado/mudou/heartbeat/
  expira/disconnect + cleanup); `tests/unit/test_transicao_service.py` (emite só no
  ramo novo, não no reenvio nem em falha).
- **@db:** `tests/integration/test_realtime_notify.py` (`pg_notify` entregue no
  commit / descartado no rollback / não duplica no reenvio; `PgEventListener` real →
  hub); `tests/integration/test_dashboard_stream_endpoints.py` (401 sem auth; 200
  `text/event-stream` + headers).
- **Web:** `apps/web/src/lib/api/eventos.test.ts` (stub de `EventSource`) +
  `dashboard-view.test.tsx` (monta/desmonta, `mudou`→refetch debounced,
  `expira`→refresh+reabre).

Rodar (@db usa a `TEST_DATABASE_URL` local):
```bash
cd apps/api && uv run pytest tests/unit/test_realtime.py tests/unit/test_dashboard_stream.py \
  tests/integration/test_realtime_notify.py tests/integration/test_dashboard_stream_endpoints.py
cd apps/web && pnpm exec vitest run src/lib/api/eventos.test.ts
```

## 7. Smoke test ao vivo (o elo que os testes automatizados não cobrem)

Sobe o backend (`uvicorn src.main:app --port 8001`) + `pnpm dev`, loga
(`admin@teste.com`/`teste123`), abre `/dashboard` e, noutra aba, cria/transiciona/
cancela uma prova → os contadores sobem **ao vivo** (count-up), sem reload. Confirma
o `EventSource` real atravessando o rewrite do Next sem buffering.
