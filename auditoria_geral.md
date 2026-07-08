# Auditoria MASTER — Sistema de Rastreio de Provas Digitais (3Studio)

> **Escopo:** auditoria **READ-ONLY** de robustez, corretude e escala, com foco na
> migração recente **Supabase → PostgreSQL local** e **Cloudflare R2 → storage local +
> ERP Firebird (read-only)**. **Nada foi alterado no código de produção.**
>
> **Data:** 2026-07-07 · **Branch:** `develop` (HEAD `4bd6e6a`) · **Alembic head:** `0024`
> **Auditor:** engenharia de supervisão (sessão Claude Code) — evidência empírica, não confiança em CHANGELOG/SESSION_LOG.

---

## 0. Veredito executivo

**Funcionalmente, a plataforma está sólida e bem testada** — a migração para banco e
storage local **não quebrou o caminho feliz**: a suíte passa 100% contra a infra REAL, o
app sobe com readiness verde, a RLS está correta e *fail-closed*, o ERP Firebird é
genuinamente somente-leitura e o storage local funciona com escrita atômica.

**Porém a plataforma NÃO está pronta para "muitas movimentações" (alto volume).** Há um
**bloco crítico de escala** que se manifesta *exatamente* quando o sistema vai para
produção — e que hoje está **mascarado em dev porque o app conecta como superuser**
(a RLS, que é a camada onde o custo explode, fica dormente). Medi empiricamente:

| Cenário (100k provas / 349k movimentações) | Hoje (dev, superuser) | Produção (RLS ligada) |
|---|---|---|
| Agregação do **Dashboard** (dispara a **cada** evento SSE) | **0,70 s** | **12,6 s** |
| Relatório **Geral** (lista de atrasadas, período "Todo") | **22,0 s** | pior ainda |
| Filtro **"Atrasadas"** na listagem | **0,67 s** | ~12 s |
| Busca por texto (ILIKE) na listagem | seq scan (~0,07 s) | idem + custo RLS |

Combine isso com o **pool de conexões desativado** (resíduo do PgBouncer do Supabase,
sem sentido no on-prem) e com o Firebird **sem timeout** no caminho de request, e o
resultado sob carga real é: **dashboard inutilizável, conexões esgotadas e a app inteira
podendo congelar**. São problemas de **configuração e de query — não de arquitetura** —
e todos têm correção conhecida. Detalhes e prioridades abaixo.

**Não corrigi nada.** Este documento lista o que precisa ser feito, em ordem.

---

## 1. Metodologia (o que foi realmente executado)

Não confiei nos documentos. Executei:

1. **Leitura de contexto:** `CLAUDE.md`, `DECISIONS.md`/ADRs, `CHANGELOG`, `SESSION_LOG`,
   `docs/firebird.md`, `docs/realtime.md`, `docs/storage.md`, e ~30 arquivos-fonte-chave.
2. **Suíte de testes REAL** — `uv run pytest --cov` com **banco + ERP Firebird + share SMB
   reais** (variáveis `TEST_DATABASE_URL`, `FIREBIRD_TEST_*`, `ARTE_SHARE_TEST_BASE`,
   `REQUIRE_DB_TESTS=1`).
3. **Inspeção do banco local** (`rastreio`): schema, enums, RLS, roles, funções `private.*`,
   reconciliação provas↔storage.
4. **Teste de carga em banco descartável** (`rastreio_audit`, clone por `TEMPLATE`):
   semeadas **100.000 provas, 349.120 movimentações, 200.014 registros de auditoria**;
   `EXPLAIN (ANALYZE, BUFFERS)` nas queries quentes, como **superuser** e como
   **`authenticated` (RLS de produção)**.
5. **Validação da RLS** como `vendedor`, `studio/admin` e sem claims (fail-closed).
6. **Revisão estática multi-agente** — 9 subsistemas × caçador de bugs + **verificação
   adversarial** por achado (46 agentes; 37 achados brutos → **12 confirmados, 7 plausíveis,
   18 refutados**).
7. **App ao vivo** — backend `uvicorn` + frontend `pnpm dev`; login real, dashboard,
   proxy de arte (inclusive **provas órfãs**), etiqueta, **leitura ao vivo do ERP**, SSE,
   console/network do navegador.

Artefatos descartáveis (scripts de seed/EXPLAIN/RLS) ficaram no scratchpad da sessão.
O banco `rastreio_audit` foi **deixado intacto para reprodução** (dropar com
`DROP DATABASE rastreio_audit;`).

---

## 2. O que está CORRETO (confirmado empiricamente)

Para calibrar a confiança — estes pontos foram verificados, não assumidos:

- ✅ **Suíte: 903 passed, 0 falhas, 0 skips, cobertura 92,96%** — e **sem skips** significa
  que os testes `@firebird`/`@share`/`@db` (incl. `test_criacao_e2e`, que cria uma prova
  real contra Firebird+share+Postgres) **rodaram contra a infra real e passaram**.
- ✅ **Readiness verde ao vivo:** `database:ok, storage:ok, erp:ok, arte_fonte:ok`.
- ✅ **RLS correta e fail-closed** (medido em `rastreio_audit`): vendedor vê só as 50.008
  provas dele; admin vê 100.010; **`authenticated` sem claims vê 0** (fail-closed real).
- ✅ **Firebird é read-only de verdade:** `TraAccessMode.READ` + `isolation=SNAPSHOT` +
  SQL só-`SELECT` parametrizado, contrato de porta sem método de escrita. Nenhum caminho
  de escrita ao ERP. Validado em código **e** ao vivo (req. 150288 → `REGISLAINE PETRIM /
  LATICINIOS FLORIDA / VERSAO_150288_V3.jpg` em 239 ms).
- ✅ **Storage local robusto:** escrita atômica (`os.replace`), anti-path-traversal,
  compensação de órfãos idempotente (`unlink(missing_ok)`); **arte órfã degrada a 404
  gracioso** (não 500, não 503-em-loop) — confirmado ao vivo.
- ✅ **Máquina de estados:** lock pessimista `FOR UPDATE` + releitura sob lock,
  `idempotency_key UNIQUE` → `IntegrityError`→409, incremento de ciclo atômico,
  `pg_notify`/`audit_log` emitidos **só no ramo de transição nova** (não no reenvio).
- ✅ **Auth ES256 própria:** rotação de refresh single-use e atômica, sem confusão de
  algoritmo (rejeita `none`/HS256-sem-segredo), `aud`/`iss`/`exp`/assinatura verificados,
  argon2id com parâmetros adequados, comparação de tempo constante, cookies **httpOnly +
  SameSite=lax** (Secure em prod).
- ✅ **Enums Python↔PostgreSQL sincronizados 1:1**; cadeia de migrations `0001..0024`
  coerente; espelhos `migrations/rls/*.sql` batem com as policies aplicadas; CHECK/unique
  parcial de `cod_vendedor_firebird` (0024) corretos.
- ✅ **SSE não segura conexão de banco** (sessão de auth curta + `NullPool`); o fan-out
  (`EventoHub`) limpa filas no `finally`; o `PgEventListener` reconecta e re-`LISTEN`.

---

## 3. Achados — ranqueados por severidade

Legenda de origem: **[E]** = medição empírica minha · **[V]** = revisão estática
verificada adversarialmente · **[E+V]** = ambas.

---

### 🔴 CRÍTICO

#### C1 — A regra "atrasada" e os relatórios usam subconsultas correlacionadas por linha; sob a RLS de produção o Dashboard vai de 0,7 s para **12,6 s**, disparado a cada evento SSE **[E+V]**
**Arquivos:** `apps/api/src/adapters/outbound/db/atraso_sql.py`,
`dashboard_repository.py`, `relatorios_repository.py`, `private.horas_uteis_entre`,
`private.instante_limite_atraso`.

**Causa raiz:** o predicado de atraso é **não-sargável** — para cada prova ativa executa
`COALESCE((SELECT max(m.created_at) FROM movimentacoes WHERE prova_id = provas.id), …)`
comparado a uma função. No `EXPLAIN`, isso é um **Seq Scan em `provas` + SubPlan
correlacionado executado 80.010 vezes**. Como superuser (dev), 0,70 s. **Sob RLS
(`authenticated`, = produção com `rastreio_runtime`), a policy de `movimentacoes`
(que espelha `provas` via `EXISTS`) é empurrada para DENTRO de cada uma das 80 mil
subconsultas → 12.604 ms** (medido). O Dashboard é **realtime**: o front rebusca
`GET /dashboard` a cada evento (debounce ~800 ms). Sob movimentação sustentada, um
refetch de 12,6 s **não acompanha** a janela de debounce → refetches se empilham e
**saturam as conexões** (agravado por C2). Relatório Geral chega a **22 s** (Q9) por
chamar `horas_uteis_entre` (plpgsql com laço dia-a-dia) **por linha** sobre a tabela toda.

**Cenário de falha:** produção com role `rastreio_runtime` (obrigatório por ADR-079) +
50k+ provas ativas + 2 telas de dashboard abertas durante um dia de operação → cada
mudança de prova dispara um refetch de ~12 s; o dashboard fica permanentemente atrasado e
as conexões esgotam.

**Direção de correção (não aplicada):** materializar o "último evento" (coluna
`provas.ultimo_evento_em` mantida por trigger/na transição, **indexada**) para tornar o
predicado sargável; e/ou índice parcial sobre provas ativas; recortar relatórios por
período por padrão e limitar a lista de atrasadas (ver M4). Reavaliar rodar a agregação
pesada do dashboard fora do caminho por-evento (cache curto + invalidação por evento).

#### C2 — `NullPool` sem PgBouncer: pooling de conexão **zerado** no on-prem (esgota `max_connections`) **[E+V]**
**Arquivo:** `apps/api/src/infrastructure/database.py:40-53` (`create_runtime_engine`).

`poolclass=NullPool`, `statement_cache_size=0`, `prepared_statement_cache_size=0`,
`pool_pre_ping=False` — **tudo justificado unicamente pelo pooler de transação do Supabase
(PgBouncer, porta 6543)**, como o próprio docstring do módulo ainda afirma. Depois da
migração on-prem para **Postgres local direto (5432), não há mais PgBouncer** — então
`NullPool` significa **abrir e fechar uma conexão física (TCP+auth+`SET ROLE`) a cada
request**, sem teto de pool e sem reuso, e **sem cache de prepared statements** (todo
query re-planeja).

**Cenário de falha:** sob concorrência (vários usuários + refetches do SSE), N requests
simultâneos abrem N conexões novas; ao passar de `max_connections` (default 100), novas
conexões falham com `FATAL: sorry, too many connections`. Combinado com as queries de 12 s
do C1, cada request lento segura uma conexão física por 12 s → colapso rápido.

**Direção de correção:** no on-prem o pooling volta para a app — trocar `NullPool` por um
pool async com backpressure (`AsyncAdaptedQueuePool` com `pool_size`/`max_overflow`) e
reabilitar os caches de statement (não há mais pooler de transação a conflitar).

> **C1 + C2 juntos são a resposta direta à sua pergunta "funcional com muitas
> movimentações?": hoje, não.** São correções pontuais (uma coluna indexada + troca do
> pool), não reescrita.

---

### 🟠 ALTO

#### A1 — Firebird **sem timeout** no caminho de request: ERP pendurado trava requests e esgota o threadpool **[V]**
**Arquivo:** `apps/api/src/adapters/outbound/firebird/requerimento_reader.py`
(uso em `application/provas.py` e `http/provas.py`).

`connect()` e `cursor.execute()` são chamados **sem timeout** e despachados por
`asyncio.to_thread` **sem `asyncio.wait_for`** (diferente do `health`, que usa
`wait_for(_CHECK_TIMEOUT_SECONDS)`). Se o servidor Firebird ficar inacessível **sem enviar
RST** (firewall dropando pacotes, ERP travado), a thread bloqueia indefinidamente segurando
a conexão; requests de criação/preview **nunca retornam** (nem 503). Após ~esgotar o
`ThreadPoolExecutor` default, **qualquer** operação que use `to_thread` (inclusive o
storage) para de responder. Risco real porque o ERP é um sistema legado de terceiros.

**Direção:** envolver as chamadas bloqueantes ao Firebird no caminho de request em
`asyncio.wait_for` com timeout, traduzindo `TimeoutError`→503; e passar timeout de
conexão/`statement_timeout` ao driver.

#### A2 — Postura de produção incompleta: app roda como **superuser** (RLS dormante), `rastreio_runtime` **sem LOGIN**, e o guard não pega bypass por **owner** (FORCE RLS ausente) **[E+V]**
**Arquivos:** `.env` (`DATABASE_URL` → `postgres`), `infrastructure/database.py`
(`_exigir_role_runtime_nao_privilegiado`), `migrations/rls/*` (sem `FORCE`).

Três fatos que se somam:
1. **Hoje o runtime conecta como `postgres` (SUPERUSER, BYPASSRLS)** — a RLS **não é
   exercida em runtime**. É tolerado em `APP_ENV=dev`, mas significa que **toda a defesa
   inferior do RBAC está desligada** no ambiente atual, e que o custo de escala do C1
   está mascarado.
2. O role correto `rastreio_runtime` (`NOBYPASSRLS`) existe mas está **sem `LOGIN`**
   (`rolcanlogin=false`) — não dá para conectar com ele ainda.
3. O guard de boot só recusa `superuser OR bypassrls`. Mas no Postgres **o OWNER da tabela
   também ignora a RLS** a menos que se aplique `FORCE ROW LEVEL SECURITY` — e **nenhuma
   migration usa FORCE**. Um role não-superuser/`NOBYPASSRLS` que seja *owner* das tabelas
   passaria pelo guard **e ainda assim faria bypass** de todas as policies.

**Cenário de falha:** ao promover para produção, ligar `rastreio_runtime` (a) dispara o
cliff de escala do C1 (12,6 s), e (b) se por engano de provisionamento esse role for owner
das tabelas, a RLS silenciosamente não vale (fail-open na camada de banco).

**Direção:** criar `rastreio_runtime` com `LOGIN` e senha (fora do repo), garantir que
**não** seja owner das tabelas, aplicar `ALTER TABLE … FORCE ROW LEVEL SECURITY` em todas
as tabelas com RLS, e estender o guard para também recusar quando `current_user` é owner
das tabelas protegidas. Fazer isso **junto** com a correção do C1 (senão o app fica lento).

---

### 🟡 MÉDIO

#### M1 — Conexão Postgres segura *idle-in-transaction* durante IO ao ERP/SMB (criação + previews) **[V]**
**Arquivos:** `application/provas.py` (`criar`), `http/dependencies.py`
(`get_requerimento_reader`, `get_provas_service`, previews).
O pré-check de idempotência (`repo.get(prova_id)`) e o *actor-load* do gate auto-iniciam
uma transação Postgres que **fica aberta durante o `to_thread(firebird.buscar)` e a leitura
do share** (segundos, se o ERP/SMB estiver lento). Com `NullPool` (C2), cada criação/preview
concorrente **pina uma conexão física** por todo o IO externo → acelera a exaustão. Correção:
encerrar a transação (rollback/commit) **antes** do IO externo, como `criar()` já faz no
caminho não-idempotente.

#### M2 — Busca por texto usa `ILIKE '%termo%'` sem índice de trigramas → seq scan por request **[E+V]**
**Arquivos:** `provas_repository.py._condicoes`, `audit_log_repository.py`.
Curinga à esquerda nunca usa btree; não há `pg_trgm`/GIN em `nome`/`cliente`/`requerimento`
(provas) nem em `motivo`/`prova_cliente`/`prova_requerimento` (auditoria). Medido: busca na
listagem = **Seq Scan removendo 100.009 linhas (~69 ms página + 59 ms count)**; auditoria =
**143 ms** (parallel seq scan em 200k). Cresce linearmente. Cada tecla (debounce 300 ms)
dispara **duas** varreduras (página + `count(*)`). Correção: `CREATE EXTENSION pg_trgm` +
índices GIN trigram (nova migration + espelho RLS).

#### M3 — `auth_sessions` cresce sem poda (nenhum DELETE de expiradas/revogadas) **[V]**
**Arquivo:** `migrations/versions/0023_auth_local.py` + `application/auth.py`.
Cada login e cada refresh faz `INSERT`; a rotação só carimba `revoked_at`, nunca deleta.
Com access TTL 30 min + refresh sliding 7 dias, cada usuário ativo gera ~48 linhas
mortas/dia. Ao longo de meses → centenas de milhares/milhões de linhas mortas; o `UNIQUE`
em `refresh_hash` e as consultas de login degradam. **Não há job de poda** (confirmado por
grep). Correção: tarefa de poda periódica no molde do `keep_alive` já existente
(`DELETE FROM auth_sessions WHERE expires_at < now() OR revoked_at IS NOT NULL`).

#### M4 — Lista de "atrasadas" do relatório Geral é **ilimitada** (sem LIMIT) **[V]**
**Arquivo:** `relatorios_repository.py` (`geral`, `atrasadas_sql`).
Seleciona **todas** as provas atrasadas, computando `horas_uteis_entre` por linha, sem
`LIMIT` (diferente do `top_motivos`, que tem `LIMIT 10`). Materializa milhares de linhas no
JSON/CSV → memória e latência ilimitadas. Correção: `LIMIT` (ex.: 100) + paginação.

#### M5 — Segredos legados vivos no `.env` (serviços abandonados) **[E]**
**Arquivo:** `apps/api/.env`.
O `.env` (corretamente fora do git) **ainda contém** chaves ativas de **Cloudflare R2**
(`R2_SECRET_ACCESS_KEY`) e a **`SUPABASE_SECRET_KEY`** — serviços que a migração abandonou.
O config nem as lê mais, mas continuam sendo material sensível em disco. Correção: **rotacionar/
revogar** essas credenciais nos provedores e removê-las do arquivo. *(A chave privada JWT
ES256 no `.env` é esperada para o on-prem, mas idealmente sairia para um secret manth.)*

#### M6 — Resíduo de dados R2→local: 2 provas com `arte_key` sem snapshot **[E]**
As provas `370baba6…` (`PRV-2026-07-9MXJX3`) e `02a87557…` (`PRV-2026-07-49Y2DY`) apontam
`arte_key` para um snapshot **inexistente** no storage local (nasceram na era R2, sem
backfill). Degrada graciosamente (404), **mas** a mensagem é `"Prova não encontrada"`
(anti-enumeração) — **enganosa**, pois a prova existe; só a arte falta. Impacto real baixo
(greenfield começa vazio), mas evidencia que a migração não reconciliou dados antigos.
Correção: backfill/limpeza desses registros; opcional, distinguir "arte indisponível" de
"prova inexistente" para o dono da prova.

---

### 🟢 BAIXO

- **B1 [V]** — Nome do arquivo temporário do upload usa só o PID
  (`filesystem_storage.py`): duas criações idempotentes concorrentes (mesmo `prova_id`, mesmo
  worker) colidem no `os.replace` → **503 espúrio** apesar do sucesso. Fix: sufixo único
  (`uuid4`/`mkstemp`).
- **B2 [V]** — Reuso de refresh token não dispara revogação da família de sessões
  (`application/auth.py`): sem detecção de roubo (RFC 9700) e sem teto absoluto no sliding
  refresh → sessão roubada renovável indefinidamente. Fix: ao ver refresh já-revogado,
  revogar toda a família do usuário.
- **B3 [V]** — Janela de perda de `NOTIFY` de ~30 s (`realtime.py`): o keepalive do listener
  dorme 30 s **antes** do `SELECT 1`, então a queda da conexão dedicada só é detectada no
  próximo probe. Mitigado pelo broadcast no reconnect, mas há atraso. Fix: callback de
  terminação da conexão.
- **B4 [E+V]** — Paginação por `OFFSET` cresce O(profundidade) no scroll infinito
  (`provas_repository.listar`): medido 20 ms no offset 20k. Baixo hoje (RLS escopa por
  usuário); migrar para keyset se o volume por perfil crescer.
- **B5 [V]** — Leitura não-atômica da arte no share (`filesystem_arte_fonte.py`): `stat` +
  `read_bytes` em duas etapas; se o fluxo legado regravar o arquivo no momento (TOCTOU),
  pode gravar snapshot **truncado** com header válido. Fix: validar completude antes de
  persistir.
- **B6 [V]** — Snapshot pode ficar inconsistente sob criação concorrente com **mesmo
  `prova_id` e requerimentos diferentes** (`application/provas.py`): a `arte_key` deriva só
  do `prova_id` e o upload precede o INSERT sem lock por chave. Fix: `pg_advisory_xact_lock`
  por `prova_id` antes do upload.
- **B7 [V]** — Desempate não-determinístico na escolha da versão da arte
  (`filesystem_arte_fonte._escolher`): empate de versão **e** `mtime` → vencedor depende da
  ordem de `iterdir()`. Contradiz a promessa de "determinístico". Fix: desempatar por nome.
- **B8 [E]** — `count(*)` recomputado a cada request da listagem (~11 ms em 100k, cresce
  linear). Considerar contagem aproximada/cacheada se o volume crescer muito.

---

### ⚪ INFO / COSMÉTICO

- **I1 [V]** — Logout não invalida o access token já emitido (janela ≤ 30 min): aceitável
  dado o TTL curto + httpOnly; fechar só se necessário (jti + denylist).
- **I2 [V]** — Convergência idempotente de transição devolve o **estado atual** da prova,
  não o estado-destino da operação reenviada. Cosmético; documentar no contrato da API.
- **I3 [E]** — Painel de boas-vindas do login ainda exibe **"Lorem ipsum silor domor amet"**
  (placeholder) em produção.
- **I4 [E]** — Docstrings/config em `database.py` ainda descrevem "pooler de transação do
  Supabase (porta 6543, PgBouncer)" — desatualizado pós-migração (relacionado a C2).
- **I5 [E]** — Warnings benignos de aspect-ratio do `next/image` (logo) no console do login.

---

## 4. Plano de ação priorizado (para produção sob volume)

**Antes de ir a produção com volume real, na ordem:**

1. **Resolver o cliff de escala (C1)** — tornar o predicado "atrasada" sargável (coluna
   `ultimo_evento_em` indexada, mantida na transição) e tirar a agregação pesada do caminho
   por-evento do SSE. **Sem isto, o dashboard não sobrevive a produção.**
2. **Religar o pooling (C2)** — trocar `NullPool` por pool async com backpressure; reabilitar
   caches de statement. Fazer **junto** com (1).
3. **Fechar a postura de produção (A2)** — `rastreio_runtime` com LOGIN e **não-owner**,
   `FORCE RLS` em todas as tabelas, guard estendido para owner-bypass. Testar o dashboard
   **sob esse role** (é onde o custo aparece).
4. **Timeout no Firebird (A1)** — `wait_for` + timeout de driver; `TimeoutError`→503.
5. **Liberar conexão antes do IO externo (M1)**, **índices trigram (M2)**, **poda de
   `auth_sessions` (M3)**, **LIMIT nas atrasadas do relatório (M4)**.
6. **Higiene de segredos (M5)** — rotacionar R2/Supabase, remover do `.env`.
7. **Backfill/limpeza das provas órfãs (M6)** e os itens BAIXO conforme capacidade.

**Regra de verificação para (1)–(3):** *toda* medição de performance deve ser feita
**conectado como `rastreio_runtime` (RLS ligada)**, não como superuser — senão o problema
volta a se esconder. O banco `rastreio_audit` (100k provas) foi deixado pronto para isso.

---

## 5. Pendências / perguntas para o dono

1. **Deploy alvo:** confirmar que produção usará `rastreio_runtime` (NOBYPASSRLS). Toda a
   priorização acima assume isso; se por acaso for manter superuser (não recomendado), o
   perfil de risco muda (RLS deixa de ser defesa).
2. **`rastreio_audit`:** deixei o banco de carga intacto para você reproduzir o 12,6 s.
   Posso dropá-lo quando quiser (`DROP DATABASE rastreio_audit;`).
3. **Servidores ao vivo:** subi `uvicorn` (:8000) e `pnpm dev` (:3000) para a auditoria —
   posso encerrá-los.
4. **Escopo de correção:** este relatório é read-only. Quando quiser, indico por qual item
   começar e trabalho por fatias verificáveis (com plano aprovado antes de cada mudança).

---

## 6. Rastreabilidade das evidências

- Suíte real: `903 passed in 306.98s`, cobertura 92,96% (log completo salvo na sessão).
- EXPLAIN em `rastreio_audit` (100k/349k/200k): Q6 Dashboard 703 ms; Q9 Relatório 22.066 ms;
  Q7 filtro atrasada 672 ms; Q3 busca 68,8 ms (seq scan).
- RLS `authenticated`: dashboard atrasadas **12.604 ms** (vs 703 ms superuser); vendedor
  50.008 provas; sem-claims 0 (fail-closed).
- Revisão multi-agente: 12 confirmados + 7 plausíveis (verificação adversarial), 18 refutados.
- App ao vivo: readiness verde; ERP req. 150288 OK; arte órfã 404 gracioso; SSE `conectado`;
  login→dashboard sem erro de console.
