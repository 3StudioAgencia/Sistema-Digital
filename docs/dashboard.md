# Dashboard em tempo real (W4-C16)

> Visibilidade operacional **fiel ao design** (layout bento), com contadores **em
> tempo real**, **clicáveis** e **escopados por perfil** (Matriz §7 via RLS),
> alimentados por **uma única subscription** do Supabase Realtime e por **uma única
> consulta de agregação** server-side. Abre a **Wave 4**.

Referências: Backlog **C16** · Requisitos **RF-015, RF-017, RF-025, RN-008,
RNF-001, RNF-011, RNF-021, RNF-022** · §7 (Dashboard = todos os perfis) · C09
(tempo de atraso) · C11 (`movimentacoes`) · C07 (listagem). Decisões: **ADR-080..085**.

---

## 1. Conjunto de contadores (reconciliado — DP-1)

O **design** mostra **5 contadores** e o dono optou por **seguir o design exato**
(ADR-080) — um **desvio consciente** do RF-015 (Must), que pede ainda "Reprovadas"
e o bloco "Em Trânsito". O desvio está registrado em `CLAUDE.md §2.1` e é
**reversível sem reescrita**: basta estender o mapeamento (`domain/dashboard.py`) e
a query de agregação. O conjunto entregue:

| Card (design) | Status mapeado (DP-2 / ADR-081) | Observação |
| --- | --- | --- |
| **Criadas hoje** | `created_at` no dia de HOJE (fuso America/São_Paulo) | qualquer status; intake diário |
| **Com Vendedor** | `retirada_vendedor` **+** `encaminhada_para_vendedor` | posse do vendedor nas 4 rotas (multi-status) |
| **Aprovadas** | `aprovada_vendedor` | estado atual |
| **Na clicheria** | `recebida_clicheria` | **= "Concluídas" do RF-015** (terminal) |
| **Atrasadas** | cálculo (ver §3) — lista por vendedor + total | ≠ dos demais (lista) |

O mapeamento vive em **`apps/api/src/domain/dashboard.py`** (`STATUS_COM_VENDEDOR`,
`STATUS_APROVADAS`, `STATUS_NA_CLICHERIA`) — fonte única que o repositório injeta na
query. Os **números do design são ilustrativos**; os valores reais vêm da agregação.

---

## 2. Agregação em consulta única (RNF-022 + mínimo de requisições)

**Uma** consulta SQL (`SqlAlchemyDashboardRepository.contadores`) devolve **todos**
os contadores + o **breakdown de "Atrasadas" por vendedor + total**, numa **única
ida ao banco**. Dentro da MESMA query:

- o **delay** do C09 (`delay_horas_uteis`, padrão 48) é lido inline do
  `system_settings` (leitura `authenticated` — C09/DP-2);
- o **instante-limite** de atraso vem de `private.instante_limite_atraso` (§3);
- os nomes do breakdown saem de `private.nomes_de_vendedores` (SECURITY DEFINER
  **escopado** — DP-7), ordenados por **contagem desc**.

A consulta roda na sessão **`abrir_sessao_rls`** (claims propagados — ADR-008): a
**RLS de `provas`/`movimentacoes` escopa cada subconsulta por perfil** (Matriz §7),
sem `WHERE` de setor no código. **Sem N+1** (teste trava: 1 SELECT em `provas` por
requisição, independente do nº de linhas/vendedores). **Sem cache** server-side.

Endpoint **`GET /dashboard`** (prefixo real **sem `/api`**) → `DashboardOut`, servido
por `get_dashboard_service` (gate **`Recurso.DASHBOARD`** — universal; o escopo é da
RLS). Página universal: qualquer perfil ativo; sem-linha/inativo → **403 genérico**
(anti-enumeração — §11).

---

## 3. "Atrasada" — horas úteis sem polling (DP-4 / ADR-083)

"Atrasada" (RN-008): prova **ATIVA** (não terminal) parada no mesmo status por mais
que o delay, medido em **horas úteis** — janela comercial **fixa seg–sex 07:00–18:00**
(RNF-011), fuso **America/São_Paulo**, **feriados fora de escopo**. Base = a **última
movimentação** (`max(movimentacoes.created_at)`) ou `created_at` se nunca movimentou.

**Truque (sem medir por linha):** como o tempo decorrido é **monotônico** no instante
do último evento, existe **um** instante-limite `L` tal que `último_evento <= L ⟺
atrasada`. `private.instante_limite_atraso(now(), delay)` recua o delay em horas úteis
e devolve `L`; a query só compara — barato, **uma chamada por consulta**. A função
(migration **0020**, schema `private` não exposto pela Data API; `STABLE`,
`SECURITY INVOKER`, `search_path=''`) é **reusada pelo filtro `atrasada` do C07**
(mesma regra → o clique no card leva à mesma contagem).

**Atualização sem polling (RNF-021):** "atrasada" muda pela **passagem do tempo**,
não por evento. Recalcula-se **na carga** e **a cada evento do Realtime** (debounced).
A defasagem (provas que "viram" atrasadas sem evento entre dois eventos) é **limitada
e aceitável** — **não** há polling. Os estados terminais (`recebida_clicheria`,
`cancelada`) são **excluídos** (derivados de `ESTADOS_TERMINAIS`, sem drift do enum).

**Breakdown escopado:** a lista por vendedor respeita a RLS — um **Vendedor** vê só a
si; **3Studio/Clicheria/Admin** veem todos.

---

## 4. Realtime único + escopo (DP-5 / ADR-084)

**UMA** subscription do Supabase Realtime às mudanças de `provas`
(`channel("dashboard-provas").on("postgres_changes", { table: "provas" })`). Cada
evento agenda um **único refetch** da agregação (debounced 800 ms) — **sem polling,
sem refetch por card, sem atualização incremental** (mais simples e seguro). O
refetch passa pelo **endpoint escopado** (RLS): mesmo que o Realtime entregue um
evento, os **números** vêm sempre da consulta escopada — nada de dado fora do escopo
trafega pela tela.

**Degradação graciosa:** a queda do Realtime **mantém o último valor** (não derruba a
tela); a carga **inicial é SSR** (sem waterfall no cliente — RNF-001 ≤ 3 s). Operação:
a `provas` precisa ter **replicação habilitada** no painel do Supabase (Database →
Replication / publication `supabase_realtime`) para os eventos dispararem; sem isso o
painel funciona com a carga SSR + refetch manual, só não recebe push.

---

## 5. UI fiel ao design + navegação (DP-6 / ADR-085)

**Layout bento** (`dashboard.module.css`, tokens `--dash-*`/`--app-*` em
`globals.css`): 4 cards de contador (clicáveis), o card **"Atrasadas"** alto (lista
por vendedor rolável + total em destaque) e os atalhos. **Count-up** (RF-025) via
`<AnimatedCounter>` (Framer Motion, `MotionValue` — anima conteúdo, não layout;
respeita `prefers-reduced-motion` → instantâneo). **Sem Recharts** (o design não tem
gráfico; não adicionamos a dependência).

**Cliques → listagem (C07) pré-filtrada (URL state):**

| Card | Navegação |
| --- | --- |
| Criadas hoje | `/provas?criada=<hoje>` |
| Com Vendedor | `/provas?status=retirada_vendedor&status=encaminhada_para_vendedor` |
| Aprovadas | `/provas?status=aprovada_vendedor` |
| Na clicheria | `/provas?status=recebida_clicheria` |
| Atrasadas (total) | `/provas?atrasada=true` |
| Atrasadas (vendedor) | `/provas?atrasada=true&vendedor=<id>` |

Para isso o **C07 ganhou** (sem regressão): filtro **`status` multi-valor**
(`?status=a&status=b` → `IN`; um valor segue simples) e o filtro **`atrasada`**
(reusa `private.instante_limite_atraso` na mesma consulta da listagem). Um **chip
"Atrasadas ✕"** aparece na barra do C07 quando o filtro chega por deep-link.

**Atalhos role-aware (RF-017 — DP-3/ADR-082):** "Escanear QR Code" (todos →
`/escanear`) e "Nova Prova" (**só 3Studio/admin** → `/provas/nova`, oculto para os
demais via `can(perfil, "criar_prova")` resolvido no servidor).

**Responsivo:** desktop bento; em ≤1100 px reflui; em ≤767 px empilha numa coluna.

---

## 6. Testes

**Backend** (`uv run pytest tests/unit/test_dashboard.py
tests/integration/test_dashboard_endpoints.py
tests/integration/test_provas_listagem_atrasada_endpoints.py` — @db, mesma
`TEST_DATABASE_URL`):

- **horas úteis** (`private.instante_limite_atraso`): 5 casos atravessando
  noite/fim de semana, janela 07–18 (parametrizados);
- contadores corretos por fixtures; **breakdown ordenado** por contagem desc;
  exclui **terminais** e usa a **última movimentação** (não o `created_at`);
- **escopo por perfil**: 3Studio/Admin todas, Vendedor só as suas (e só a si no
  breakdown), Motorista só "Em Trânsito";
- **sem N+1** (1 SELECT em `provas`); 401 sem token; 403 genérico não-provisionado;
- **C07**: `status` multi-valor (`IN`), `status` único intacto, filtro `atrasada`
  (só ativas+velhas), `atrasada` + `status` combinados.

**Frontend** (`pnpm test` — `dashboard-view.test.tsx`): render fiel (5 cards +
Atrasadas lista+total + atalhos), count-up (aria-label), **UMA** subscription +
cleanup, evento Realtime → **um** refetch debounced + atualização, **degradação
graciosa** (mantém valor na falha), cliques → deep-links (multi-status; atrasada+
vendedor), atalho "Nova Prova" oculto para não-3Studio, carga sem SSR.

---

## 7. Checklist dos critérios de aceitação (§6 do prompt)

- [x] **Fiel ao design** (bento, cards, Atrasadas lista+total, atalhos) — conjunto
      reconciliado (DP-1: design exato; desvio do RF-015 registrado).
- [x] **Tempo real** com **count-up** via **uma** subscription — **sem polling/refetch
      total** (RNF-021).
- [x] **Agregação server-side em consulta única** (RNF-022), **sem N+1**; carga ≤ 3 s
      (SSR — RNF-001).
- [x] **Escopo por perfil** (RLS) — incl. a lista de atrasadas (Vendedor só a si).
- [x] **"Atrasada"** em **horas úteis** (seg–sex 07–18) com o **limiar do C09**, base
      na última movimentação; sem polling (DP-4).
- [x] **Cliques** → listagem pré-filtrada (incl. "Atrasadas"); **atalhos** por perfil.
- [x] **Count-up** + `prefers-reduced-motion`; degradação graciosa; **responsivo**.
- [x] Testes do **C07 verdes** (sem regressão).
- [x] **Stateless**; sem segredos versionados; **R$ 0**;
      `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build`/`prettier` verdes; migration
      `0020` com `upgrade`/`downgrade` limpos.
