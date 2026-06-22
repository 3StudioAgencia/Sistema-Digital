# Log de Auditoria (W6-C20)

> Interface read-only, **exclusiva do 3Studio**, sobre um **log imutável de todas as
> ações do sistema**. Último componente do backlog v1.0. Fecha a Wave 6.

## 1. Escopo e fonte do log (DP-1 = C — ADR-100)

O design elevou a aposta do RNF-006: de "janela para as movimentações" (`movimentacoes`
do C11) para **"log imutável de todas as ações do sistema"**, com **eventos que não são
movimentação** (criação, escaneamento), **Endereço IP**, **Origem** (navegador) e um
**hash de integridade encadeado**. O dono escolheu conscientemente a **opção (C)**: uma
tabela própria **`audit_log`** que **unifica**:

- **transições** da máquina de estados (C11/C14/C15) — `mudou_status`, `aprovou_prova`,
  `reprovou_prova`, `reiniciou_ciclo`, `cancelou_prova`;
- **criação de prova** (C06) — `criou_prova`;
- **escaneamento/identificação** (C10) — `escaneou_qr`;

com **IP/Origem** (capturados no middleware) e um **chain SHA-256** de tamper-evidence.

> **`movimentacoes` (C11) NÃO foi tocado.** A Timeline por-prova (C13) segue lendo de lá;
> `audit_log` é uma estrutura PARALELA, desacoplada e auto-contida. Eventos periféricos
> (login, mudança de config) ficaram **adiados** (não essenciais ao design) — registrado
> como pendência, sem expandir mais o escopo.

## 2. Tabela `audit_log` (migration 0022)

Append-only, auto-contida (campos de prova/ator **denormalizados** — o log registra o
que era verdade no instante e é pesquisável sem JOIN). Colunas principais:

| coluna | papel |
| --- | --- |
| `seq` (bigint, unique) | ordem do chain (monotônica; atribuída sob o advisory lock) |
| `evento` (`audit_evento_enum`) | um dos 7 tipos (1:1 com `domain/auditoria.py`) |
| `ator_id` / `ator_setor` | ator (forçado das claims) + setor no instante (denormalizado) |
| `prova_id`/`prova_codigo`/`prova_cliente`/`prova_requerimento` | prova denormalizada (nullable) |
| `acao`/`estado_origem`/`estado_destino`/`ciclo` | só nos eventos de transição |
| `motivo` | reprovação/cancelamento |
| `ip`/`origem_user_agent`/`origem_rotulo` | origem (best-effort, do middleware) |
| `request_id` | correlação com os logs estruturados (RNF-024) |
| `prev_hash`/`hash` | elo do chain (SHA-256 de `prev_hash \|\| campos`) |
| `created_at` | carimbo imutável |

**Imutabilidade em DUAS camadas:** trigger `trg_audit_log_append_only` (bloqueia
UPDATE/DELETE **até para o owner**) + **ausência de GRANT** UPDATE/DELETE.

## 3. Escrita: a única porta é a função `private.audit_log_append` (SECURITY DEFINER)

`authenticated` **não tem INSERT direto** em `audit_log` (anti-forja do chain). A escrita
passa **exclusivamente** pela função `private.audit_log_append(...)` (SECURITY DEFINER,
`search_path=''`, corpo schema-qualificado — blindagem W1-A-004), que:

1. **força** `ator_id = app_current_user_id()` e `ator_setor = app_setor()` (o cliente
   não escolhe o ator — fail-closed se não houver `user_id` nas claims);
2. serializa o chain com **`pg_advisory_xact_lock(8423712001)`** (um append por vez — dois
   eventos concorrentes nunca leem o mesmo head e bifurcam o encadeamento). É o **último
   lock** adquirido em todos os caminhos (criação/transição/escaneamento) → **sem ciclo de
   deadlock**;
3. lê o head (`seq`/`hash` do último), calcula `seq+1`, `prev_hash` e `hash` via a função
   **`private.audit_log_hash`** (fonte ÚNICA do cálculo — usada por append E verificar, sem
   drift de canonicalização) e INSERE.

O **hash** é determinístico entre sessões: o `created_at` entra como
`extract(epoch from ...)` (instante absoluto, **independente do timezone da sessão** — um
`::text` de timestamptz dependeria do GUC `timezone`).

> **Trade-off (escalabilidade):** o advisory lock global serializa TODAS as escritas que
> produzem evento. É aceitável para o volume desta app (rastreio de provas de um print
> shop). Se a vazão crescer, dá para particionar o chain.

### Verificação de integridade (DP-4)

`private.audit_log_verificar()` (SECURITY INVOKER — admin lê tudo pela RLS) **recomputa o
chain** e devolve `(intacto, total, quebrou_em)`, onde `quebrou_em` é o `seq` da **1ª linha
divergente** (`NULL` quando íntegro). Alterar a linha N (mesmo desativando o trigger, como
faria um ataque direto ao banco) **quebra a verificação exatamente em N** — coberto pelo
teste `test_audit_log_integridade.py`.

## 4. Captura (efeito colateral atômico, sem mudar a regra dos componentes)

A captura é um **efeito colateral** dos casos de uso, injetado via `AuditLogPort` (porta de
aplicação) — opcional (`audit=None`) para não quebrar os testes que não a exercem. **Logar
não muda a regra** dos componentes:

- **Criação (C06):** `criou_prova` na **MESMA transação** do INSERT da prova (atômico — uma
  colisão de código no commit descarta também o evento; a retentativa registra o evento da
  prova que de fato persistir → exactly-once);
- **Escaneamento (C10):** `escaneou_qr` **só no sucesso** da resolução — o 404
  (malformado/inexistente/fora-de-escopo) **não loga nada** (anti-enumeração RN-014);
- **Transições (C11/C14/C15):** o evento mapeado (`EVENTO_POR_ACAO`) na **MESMA transação**
  da movimentação; o reenvio **idempotente** cai no ramo "existente" e **NÃO duplica** o
  evento.

IP/User-Agent são capturados no **middleware** (`RequestIdMiddleware`) em ContextVars
(`client_ip_var`/`user_agent_var`), lidos pelo adapter ao gravar. **Best-effort:** preferem
`CF-Connecting-IP` → 1º salto de `X-Forwarded-For` → peer direto; é **metadado de origem**,
**nunca** uma decisão de acesso (a confiança real depende do edge sobrescrever esses
headers). O `origem_rotulo` ("Aplicação Web · Chrome") vem de `rotulo_origem(user_agent)`
(heurística leve, sem dependência nova — R$ 0).

## 5. Acesso 3Studio em DUAS camadas

`Log de Auditoria` é "Exclusivo 3Studio" (Matriz §7 ●○○○ — flag `administrador`, ADR-023).
O recurso **`log_auditoria`** já existia nos 3 espelhos RBAC (`access-matrix.cells.json`,
`access-matrix.ts`, `domain/rbac.py`) e a rota `/auditoria` já mapeava para ele → **não há
PR de Matriz**. As duas camadas:

- **Superior:** o `proxy.ts` (via `podeAcessarRota`) redireciona o não-admin e a **sidebar**
  esconde o item (filtra por `log_auditoria`).
- **Inferior:** o endpoint gateia por `Recurso.LOG_AUDITORIA` (→ 403) **e** a RLS
  `audit_log_select_admin` = `app_is_admin()`. Negar em qualquer camada basta.

## 6. Endpoints (prefixo real `/auditoria`, SEM `/api`) — read-only

| método | rota | papel |
| --- | --- | --- |
| GET | `/auditoria` | listagem paginada/filtrada (master-detail) — server-side, sem N+1 |
| GET | `/auditoria/atores` | atores distintos do log (dropdown "Ator") |
| POST | `/auditoria/verificar-integridade` | recomputa o chain (read-only: não altera nada) |

Filtros (DP-2): `evento` (multi), `ator_id`, `busca` (motivo/cliente/nº requerimento),
`de`/`ate` (período por dia, UTC), `ordem` (recentes/antigos por `seq`), `page`/`page_size`
(teto 200, default 50). O nome do ator é resolvido por **LEFT JOIN a `usuarios`** (o
chamador é admin — vê todos), em uma única consulta (sem N+1).

## 7. Frontend (`/auditoria`)

`AuditoriaView` (client) — **master-detail fiel ao design**: cabeçalho + barra de filtros
(presets/Eventos/Ator/Ordem/busca/De/Até/Linhas, estado na URL reusando o C07, busca com
debounce ≥300ms) + lista rolável (ponto colorido por tipo — `lib/auditoria/evento-labels.ts`)
+ painel de detalhe (Ator/Setor/Prova/Endereço IP/Origem/Data e hora + rodapé "Registro
íntegro e imutável" com `sha256:…`). Paginação por **scroll infinito**. No **mobile**, lista
→ detalhe em **drill-in**. Botão **"Verificar integridade"** (toast com o veredito).
Animações via C19 (só `transform`/`opacity`, `prefers-reduced-motion`). **Honestidade de
dados:** campos ausentes mostram "—" (nunca IP/origem/hash falsos).

## 8. Testes

**Backend** (`@db`, `TEST_DATABASE_URL`):
```
uv run pytest tests/unit/test_auditoria_dominio.py \
  tests/unit/test_equivalencia_rls_audit_log.py \
  tests/integration/test_audit_log_captura.py \
  tests/integration/test_audit_log_integridade.py \
  tests/integration/test_auditoria_endpoints.py \
  tests/integration/test_rls_audit_log.py \
  tests/integration/test_migrations.py
```
Cobre: captura (criação/escaneamento/transições/cancel) + idempotência (sem duplicar) +
anti-enumeração (404 não loga); RLS (admin-only SELECT, INSERT direto negado, append-only);
integridade (chain íntegro + **detecção de adulteração**); endpoints (filtros/paginação/
atores/verify/403/read-only/captura de IP-origem). **Web:** `pnpm test`
(`evento-labels.test.ts`, `auditoria-view.test.tsx`).

## 9. Checklist (critérios §6 do prompt)

- [x] Tela fiel ao design (cabeçalho+subtítulo; filtros; master-detail com color-coding;
      detalhe; rodapé de integridade com hash).
- [x] Acesso restrito ao 3Studio em duas camadas (gate + RLS → 403; sidebar/proxy).
- [x] Reprovações, reinícios, cancelamentos e travessias de motorista visíveis (RNF-006).
- [x] Read-only — nenhuma mutação; imutabilidade estrutural + chain verificável.
- [x] Filtros/busca/ordenação/paginação server-side; sem N+1.
- [x] Sem campos não-habilitados/falsos (IP/origem/hash existem de verdade).
- [x] Captura sem alterar a regra dos componentes; migration/RLS aditivas e limpas.
- [x] Stateless; sem segredos versionados; R$ 0; ruff/mypy/pytest/pnpm verdes.

## 10. Pendências adiadas (auditoria — futura wave)

- Eventos periféricos: **login/logout** e **mudança de configuração** (C09) ainda não
  geram evento. A camada está pronta (`AuditLogPort` + a função append) — basta chamar o
  registrar nos novos pontos.
- O chain é **SHA-256 sem segredo** (tamper-EVIDENT contra alteração parcial; o append-only
  do banco é a barreira primária). Endurecimento opcional: HMAC com chave em env para
  resistir a um rewrite total por quem tenha acesso de escrita ao banco.
