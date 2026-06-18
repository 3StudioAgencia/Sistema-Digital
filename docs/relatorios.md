# Relatórios gerenciais (W5-C17)

> Seção de relatórios **exclusiva do 3Studio** (flag `administrador`), **fiel ao
> design** (4 abas, filtros compartilhados, gráficos Recharts, tabelas, **export
> CSV**), com agregação **server-side por aba** (lazy, sem N+1) reusando a **função
> de horas úteis** e o **predicado de "Atrasada"** do C16, **sem Realtime** (snapshot
> do período). Abre a **Wave 5**.

Referências: Backlog **C17** · Requisitos **RF-016 (Should), US-014, RNF-001,
RNF-011, RNF-022** · §6 (estados/rotas) · §7 (Relatórios = "Exclusivo 3Studio") ·
C16 (horas úteis + agregação) · C11 (`movimentacoes`) · C09 (delay) · C07 (filtros).
Decisões: **ADR-086..093**.

---

## 1. Acesso (DP-7) — exclusivo 3Studio, duas camadas

A Matriz §7 marca **Relatórios** como **"Exclusivo 3Studio"** (●○○○) — idêntico a
*Configurações* e *Cadastro de Usuários*. Pela ADR-023, essas linhas chaveiam pela
**flag `administrador`** (ortogonal ao setor): um Vendedor-com-admin vê os
relatórios; um 3Studio não-admin, não. **Nada novo na Matriz** — `Recurso.RELATORIOS`
já existia nos três espelhos (`access-matrix.cells.json`, `access-matrix.ts`,
`domain/rbac.py`) + item de menu + proxy.

Duas camadas (RN-013):
- **Superior:** `proxy.ts` (rota `/relatorios` → `can(perfil, "relatorios")`) + a
  sidebar esconde o item para não-admins.
- **Inferior:** `get_relatorios_service` gateia por `Recurso.RELATORIOS` →
  **403** ao não-admin. **Os endpoints de agregação E de export** passam por ele
  (a borda barra antes de qualquer consulta). Os números são escopados pela RLS de
  `provas`/`usuarios` (na prática, todos — o ator é admin).

---

## 2. Filtros compartilhados (DP-4)

Estado em **URL** (refresh-safe, compartilhável; reusa os padrões do C07:
`useSearchParams` + `router.replace` + debounce ≥300 ms na busca). A barra é a
mesma em todas as abas; trocar de aba ou de filtro **recomputa** a aba ativa.

| Filtro | Param URL | Backend | Observação |
| --- | --- | --- | --- |
| Período De/Até | `de` / `ate` | `created_at >= de` e `< ate+1d` (dia UTC) | recorta a **população** |
| Presets | (preenchem `de`/`ate`) | — | Hoje / 7d / 30d / 90d; edição manual prevalece |
| Status | `status` (multi) | `status IN (...)` | dropdown dos 14 |
| Rota (toggle 2-vias) | `rota` = `""`/`matriz`/`filial` | `rota IN (...)` (multi) | **grupo** → `Matriz`={matriz, lam_matriz}, `Filial`={filial, lam_filial} |
| Busca | `busca` | `nome ILIKE` **OU** `requerimento ILIKE` (RF-013) | "nº requerimento" = coluna `provas.requerimento`, **não** o código PRV |
| Vendedor | `vendedor` | `vendedor_id = ...` | dropdown escopado (`GET /provas/vendedores`) |

**População base (decisão de engenharia — ADR-091):** o período recorta as provas
por **`created_at`** (provas *criadas* na janela); os demais filtros compõem com ele.
**Toda métrica de cada aba** é calculada sobre essa MESMA população (definição única
e consistente). A **distribuição por rota soma o total da base** (critério §6.3 — 100%
no período).

---

## 3. Métricas por aba — fórmulas confirmadas (DP-3, ADR-088)

Fonte única das fórmulas: **`apps/api/src/domain/relatorios.py`**. Base temporal =
**HORAS ÚTEIS** (seg–sex 07–18, America/São_Paulo — RNF-011), a MESMA do C16.

### Aba Geral (§0.2) — piso do RF-016 + extras
- **Total geral** = `count(base)`; gráfico de **volume** = provas/dia (`created_at::date`).
- **Tempo médio de aprovação** (geral e por vendedor) = horas úteis entre a **chegada
  ao vendedor** (transição p/ `retirada_vendedor`/`encaminhada_para_vendedor`) e a
  **aprovação** (`acao=aprovar`). Âncora = chegada-ao-vendedor (ADR-088).
- **Taxa de reprovação** = `reprovadas ÷ (aprovadas + reprovadas)` (eventos no período);
  `null` (→ "—") sem decisões. Corroborada pelo design (Aprov% + Reprov% = 100%).
- **Distribuição por rota** = `count(base)` por rota (as **4** sempre, soma 100%).
- **Provas Ativas (donut)** = 2 segmentos: *Aguardando vendedor*
  (`retirada_vendedor`+`encaminhada_para_vendedor`) vs *Reprovada* (`reprovada_vendedor`).
- **Atrasadas** = MESMA regra do C16 (`private.instante_limite_atraso` + delay do C09);
  **atraso exibido em horas úteis** (DP-3: unidade = horas, fiel ao design).
- **Métricas por vendedor** (tabela) — volume, aprovadas, reprovadas, taxa, tempo,
  atrasadas. O front DERIVA "Tempo médio por vendedor" e "Vendedor com mais artes"
  reordenando esta lista (sem ida extra).

### Aba 3Studio (§0.2)
- **Provas criadas** = `count(base)` (+ **média diária** = criadas ÷ dias do período);
  o card preto "Provas Criadas" exibe a **série `volume`** (provas/dia, `created_at::date`)
  como gráfico de barras, igual ao Total geral da Geral (ADR-094).
- **Reinícios** = `acao=reiniciar_ciclo`; **Cancelamentos** = `acao=cancelar`.
- **Devolvidas** = **reprovações no período** (`acao=reprovar`) — ADR-088.
- **Reprov. aguardando** = status atual `reprovada_vendedor`.
- **Tempo até 1ª mov.** = horas úteis de `created_at` à 1ª movimentação.
- **Top motivos de cancelamento** = `movimentacoes.motivo WHERE acao=cancelar`
  (não há tabela de motivos separada — o log é o `movimentacoes`), top 10 desc.

### Aba Vendedores (§0.2)
- **Provas criadas** = `count(base)` + **série `volume`** (provas/dia) — card preto
  "Provas Criadas" com gráfico (igual à Geral/3Studio; campos `provas_criadas`/`volume`
  **adicionados** na sessão de design — ADR-094).
- **Ranking por volume** (lista ranqueada, barra ∝ volume) + **Detalhamento** full-width
  (Aprov% = 100−taxa, Reprov%, Tempo, Atrasadas).
- `vendedores_filial`/`vendedores_matriz` (usuários `setor=vendedor` ativos por
  localização — cadastro), `ativos` (distintos com prova na base) e `atrasadas_total`
  **seguem no payload e no CSV**, mas o **card "Vendedores Filial" saiu da UI**
  (ausente no design — ADR-094).

### Aba Clicheria (§0.2 — perspectiva "rumo à clicheria", ADR-088)
- **Em trânsito agora** = `com_motorista_entrega_final`.
- **Recebidas no período** = `recebida_clicheria`.
- **Tempo médio aguardando** = horas úteis do **envio** (transição p/
  `com_motorista_entrega_final`) ao **recebimento** (`recebida_clicheria`).
- **Origens** = nº de rotas distintas entre as recebidas; **distribuição por rota
  de origem** = recebidas por rota (empty state "Nenhuma prova recebida no período").

---

## 4. Agregação server-side (DP-6, ADR-090) — reuso do C16

Uma **operação por aba** (`RelatoriosRepositoryPort`), cada uma em **poucas consultas
SET-BASED** (sem N+1 — RNF-022), sob `abrir_sessao_rls`. **Lazy:** o endpoint serve
uma aba por requisição; o front monta só a aba ativa → só ela busca. **Sem Realtime**
(§2): snapshot do período, recomputado na troca de filtro/aba. ≤ 3 s (RNF-001).

**Reuso (não reinventa — §3.1):**
- "Atrasada" reusa `SQL_PREDICADO_ATRASADA`/`SQL_ULTIMO_EVENTO` do C16 **verbatim**
  (consistência — critério §6.5) + `private.instante_limite_atraso` (0020).
- Tempos em horas úteis via **`private.horas_uteis_entre(inicio, fim)`** (migration
  **0021**, schema `private`, `STABLE`/`SECURITY INVOKER`/`search_path=''`; espelho
  `migrations/rls/horas_uteis_entre.sql`) — soma a interseção de `[inicio, fim]` com
  a janela comercial de cada dia. Complementa a 0020 sem substituí-la.

**Segurança do SQL:** os filtros interpolam só valores de **enum validados**
(status/rota — o FastAPI já converteu) e nunca entrada crua; busca/datas/uuid entram
como **bind params** (`:busca`, `CAST(:de AS date)`, etc.).

Arquivos: `application/relatorios.py` (serviço + CSV), `adapters/outbound/db/
relatorios_repository.py` (SQL), `adapters/inbound/http/relatorios.py` (endpoints),
`get_relatorios_service` em `dependencies.py`.

---

## 5. Export CSV (DP-5, ADR-089)

`GET /relatorios/exportar?aba=<aba>&<filtros>` → CSV da **aba ativa**, preservando
**todos os campos exibidos** e respeitando os **filtros ativos** (reusa a mesma
agregação da tela). **UTF-8 com BOM + separador `;`** (abre direto no Excel pt-BR,
acentuação e colunas corretas; decimais com vírgula). O botão **Exportar CSV** tem
**caret** → menu para escolher a aba. Gate `RELATORIOS` (403 ao não-admin). Os
rótulos de status/rota no CSV espelham os do front (`status-labels.ts`/`rota-labels.ts`).

---

## 6. Endpoints

| Método | Rota | Resposta |
| --- | --- | --- |
| GET | `/relatorios/geral` | `RelatorioGeralOut` |
| GET | `/relatorios/studio` | `RelatorioStudioOut` |
| GET | `/relatorios/vendedores` | `RelatorioVendedoresOut` |
| GET | `/relatorios/clicheria` | `RelatorioClicheriaOut` |
| GET | `/relatorios/exportar?aba=…` | `text/csv` (attachment) |

Prefixo real **`/relatorios`** (sem `/api`). Todos 3Studio-only (403 caso contrário).

---

## 7. Frontend

`apps/web/src/app/(app)/relatorios/` — `page.tsx` (Suspense + `RelatoriosView`),
`error.tsx` (boundary), `relatorios.module.css`, `_components/` (view, 4 tabs,
`charts.tsx` Recharts, `widgets.tsx`, `use-relatorio.tsx`). Tipos/fetch em
`lib/api/relatorios.ts`; formatação em `lib/relatorios/format.ts`.

- **Recharts** (3.x — adicionado nesta wave; **não** existia, apesar do que o prompt/
  CLAUDE.md §4 afirmavam — ADR-092): barras de volume + donut de provas ativas.
  Distribuição/ranking/motivos = barras CSS (`scaleX`, GPU). Animações respeitam
  `prefers-reduced-motion` (`isAnimationActive`/tokens). Tabelas roláveis no mobile.
- `<AnimatedCounter>` (count-up) nos números inteiros; métricas sem base → "—".
- **Layout fiel ao Figma (ADR-094):** cada aba é um **bento (grid 12 col)** — Geral,
  3Studio e Vendedores reconstruídas em sessão de design (cabeçalho/filtros com pílula
  deslizante, **campo de data como trigger** do calendário, `Dropdown` variante `branco`
  + scrollbar fino; `VolumeBars` densas por **binning**; donut com **espessura radial**
  via dois `<Pie>`). **Pendente:** a aba **Clicheria** ainda usa `widgets.tsx`
  (`StatCard`/`ListaBarra`) — próxima a reconstruir.

---

## 8. Testes

**Backend** (`uv run pytest`):
- `tests/unit/test_relatorios.py` — CSV (BOM + `;` + campos + acentuação), `_taxa`,
  `dias_no_periodo`, zero-fill das rotas (offline).
- `tests/integration/test_relatorios_endpoints.py` (@db) — `private.horas_uteis_entre`
  (parametrizado), as 4 abas com fórmulas conferidas, **distribuição soma 100%**,
  atrasadas **consistente com o C16**, filtros (rota multi/vendedor/status/período),
  **403 não-admin** em todas as abas + export, **CSV** (BOM, campos, respeita filtros).
- `tests/integration/test_migrations.py` — head **0021** + criação/remoção de
  `private.horas_uteis_entre`.

**Frontend** (`pnpm test`): `relatorios-view.test.tsx` — render do shell + 4 abas +
Exportar CSV; **lazy** (só a aba ativa busca); troca de aba escreve `?aba=` na URL;
export dispara o download; preset escreve De/Até.

Comando @db: `REQUIRE_DB_TESTS=1 uv run pytest tests/unit/test_relatorios.py
tests/integration/test_relatorios_endpoints.py tests/integration/test_migrations.py`.

---

## 9. Checklist dos critérios de aceitação (§6)

- [x] Relatórios **apenas para 3Studio** (proxy/UI **e** endpoints → 403).
- [x] Todas as métricas do **RF-016** presentes (tempo médio geral+vendedor, total
  por vendedor, atrasadas, total geral, taxa de reprovação, distribuição por rota, CSV).
- [x] **Distribuição por rota soma 100%** no período filtrado.
- [x] **CSV preserva todos os campos exibidos** e respeita os filtros.
- [x] Métricas respeitam todos os filtros; base temporal = **horas úteis**,
  **consistente com o C16** (mesma função de atraso).
- [x] **Fiel ao design** (4 abas, cards, Recharts, tabelas, empty states, Exportar CSV);
  **agregação por aba lazy** (não calcula as 4 de uma vez); ≤ 3 s.
- [x] **Sem Realtime**; animações com `prefers-reduced-motion`; responsivo.
- [x] Stateless; sem segredos versionados; R$ 0; ruff/mypy/pytest/lint/build verdes;
  migration `upgrade`/`downgrade` limpa.
