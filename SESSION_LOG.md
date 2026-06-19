# SESSION_LOG.md

> Diário cronológico de sessões de trabalho. Cada sessão = um componente (em geral). Entrada mais recente no topo.
> Preenchido ao final de cada sessão pelo **Protocolo de Encerramento** (`CLAUDE.md §10`).

---

## Modelo de entrada (copiar para cada nova sessão)

```
## Sessão NN — AAAA-MM-DD — [Wave X / Componente CYY] Título

**Objetivo:** (o componente/escopo da sessão)

**Feito:**
- ...

**Decisões (ADRs):**
- ADR-XXX: ... (link/ref em DECISIONS.md)

**Testes / cobertura:**
- ...

**Pendências / em aberto:**
- [ ] ...

**Próximo passo:**
- (próximo componente conforme dependências do Backlog)

**Definition of Done:** (✅ atendida / ⚠️ parcial — detalhar)
```

---

## Sessão 25 — 2026-06-19 — [Wave 5 / Remediação] Fechamento dos achados do `AUDITORIA-WAVE-5.md`

**Objetivo:** Reverter o **NO-GO** da Wave 5 fechando os achados do relatório de fechamento (`docs/audits/AUDITORIA-WAVE-5.md`) — causa raiz, sem regressão, com o corte do C18 limpo. Sessão dirigida pelo relatório.

**Feito (executar, não confiar):**
- Subi o cluster Postgres de teste (`.tmp-pg` na 5432, estava parado) → testes @db rodam.
- **F-02 (Alto) — RESOLVIDO:** `ruff check .` (corrigi `F841 p_hoje_transito` preservando o seed) + `ruff format .` (17 arquivos) → ambos os gates **verdes** + `mypy` ✅. Suíte api **807 passed** logo após a reformatação (sem regressão).
- **F-01 (Crítico) — RESOLVIDO:** produzi **`docs/audits/AUDITORIA-C17.md`** via workflow adversarial (12 áreas com auditor+cross-check independentes + crítico de completude) **+ recomputação do auditor humano** + suíte @db. **Veredito GO.** A auditoria **descobriu o M-1** (time-bomb): a fixture `ctx` datava eventos de provas ATIVAS em `2026-06-15` fixo enquanto "Atrasada" usa `now()` → a partir de ≈ sex 19/06 **15:00** elas virariam atrasadas e quebrariam 3 testes (confirmei por query: 43,36h úteis às 10:21, limiar 48h). **Corrigi a causa raiz** (âncora `_ancora_comercial`/`_em` → dia útil recente, gaps 2h/4h preservados) + **guard determinístico**.
- **F-03/F-04/F-05 (Médios) — RESOLVIDOS:** **ADR-095** (corte do C18); docs sincronizados (C18 **descartado**; Clicheria reconstruída `9e3fbde`; claims de qualidade reconciliados). **F-06 (Baixo) — RESOLVIDO** (`prettier --write`). **F-07 (Baixo) — mantido por design** (barras estáticas não são defeito; animar é decisão do dono → eventual W6-C19).
- **Guardrails:** novo `test_integracao_atrasadas_c16_c17.py` prova "Atrasadas" igual em dashboard **e** relatório (dois lados); `dashboard-view.test.tsx` ganhou guard do corte do C18.
- Atualizei o `AUDITORIA-WAVE-5.md` (banner de remediação + STATUS por achado).

**Decisões (ADRs):**
- **ADR-095** — corte do C18 (Atalhos Rápidos) por decisão de produto. Aceita.
- (M-1 e demais correções são de teste/higiene — sem novo ADR; o predicado/fórmulas do C17 não mudaram.)

**Testes / cobertura:**
- api: suíte completa **813 passed** (`REQUIRE_DB_TESTS=1`, PG `.tmp-pg` 5432); `ruff check`/`ruff format --check`/`mypy --strict` **verdes**.
- web: `vitest` **179 passed** (27 files, +1 guard do corte do C18); `lint`/`build`/`format:check` **verdes**.

**Pendências / em aberto:**
- [ ] B-1/B-3 do `AUDITORIA-C17.md` (cobertura de `tempo_ate_primeira_mov`/`media_diaria`) — Baixos, opcionais.
- [ ] Aplicar (já aplicada) — sem migration nova nesta sessão; head segue `0021`.

**Próximo passo:**
- **Re-auditar a Wave 5** (a palavra final do GO é da re-auditoria). Comando sugerido: rodar a auditoria de fechamento da Wave 5 novamente sobre `develop`. Se **GO** → **W6-C19 · Camada Transversal de Animações** (abre a Wave 6). **C18 descartado** (ADR-095) — não construir.

**Definition of Done:** ✅ suíte verde (api 813 / web 179), gates verdes, integração intacta (dois lados), corte do C18 limpo (código + docs), sem regressão, sem migration nova (head `0021`), sem segredos versionados. Falta a re-auditoria confirmar o GO.

---

## Sessão 24 — 2026-06-19 — [Wave 5 / Fechamento] Auditoria de fechamento da Wave 5 (read-only)

**Objetivo:** Emitir o veredito Go/No-Go da Wave 5 **no nível de sistema** — incorporar (não repetir) o veredito da auditoria dedicada do C17, e cobrir integração, regressão, limpeza do corte do C18 e qualidade transversal. **Sem alterar código de produção.**

**Feito (executar, não confiar):**
- Rodada a suíte inteira do `api`: `pytest -q` (REQUIRE_DB_TESTS=1, PG `.tmp-pg` 5432) → **807 passed**, exit 0 (sem regressão Waves 0–4). `mypy` → Success (98 files). Round-trip de migrations coberto por `test_migrations.py` (head **0021**, verde).
- Web: `vitest` **178 passed** (27 files), `pnpm lint`/`build` verdes.
- **Gate de lint/format reproduzido equivalente à CI** (`uv sync --frozen`, ruff 0.15.16): `ruff check .` = **16 erros** (W4, pré-existente) e `ruff format --check .` = **17 arquivos** (inclui fontes do C17) → o job `api` da CI falha no passo de lint (`ci.yml:71-72`).
- Confirmado **reuso verbatim do C16** (`atraso_sql.py` compartilhado por dashboard/relatórios/listagem; `horas_uteis_entre` aditiva → "Atrasadas" bate por construção), **acesso a Relatórios coerente** (cells.json/access-matrix.ts/rbac.py travados por equivalência; proxy + 403 backend), e **corte do C18 limpo no código** (sem CTA a relatórios fora da sidebar, sem sobra órfã; atalhos Escanear/Nova Prova do C16 autônomos).
- Verificação read-only conduzida com fan-out (workflow de 6 agentes) + checagens próprias. Relatório em `docs/audits/AUDITORIA-WAVE-5.md`; evidências em `audit/logs/`.

**Veredito:** **⛔ NO-GO.** Contagem: **1 Crítico · 1 Alto · 3 Médios · 2 Baixos.**
- 🔴 **Crítico** — `docs/audits/AUDITORIA-C17.md` **ausente** (insumo principal): por §A3 do prompt, relatório do C17 ausente ⇒ Wave 5 NO-GO automático.
- 🟠 **Alto** — gate `ruff check` + `ruff format` vermelho → CI do `api` falha (D1/§5d).
- 🟡 **Médios** — corte do C18 não registrado (dívida fantasma; sem ADR); docs stale (Clicheria já reconstruída no commit `9e3fbde`); claims "ruff/format/prettier limpos" falsos.
- ⚪ **Baixos** — `nova-prova-view.tsx` não commitado deixa prettier local vermelho; barras CSS do C17 sem `transition` (estáticas, seguro).

**Corte do C18:** confirmado **limpo no código** (C1/C2/C3 PASSA), mas **não documentado** (C4 FALHA) — recomendado (não implementado) um ADR formalizando o corte e a marcação do C18 como descartado nos roadmaps.

**Decisões (ADRs):** nenhuma (auditoria read-only). **Recomendação registrada no relatório, não implementada:** ADR de corte do C18.

**Pendências / em aberto (para reverter o NO-GO, em ordem):**
- [ ] Rodar/fechar a **auditoria dedicada do C17** (`docs/audits/AUDITORIA-C17.md`).
- [ ] Limpar lint/format (`ruff check --fix` + E501 + `ruff format .`) até a CI verde.
- [ ] Registrar ADR do corte do C18 + sincronizar os 5 docs (C18 descartado; Clicheria reconstruída; remover claims "limpos").
- [ ] Re-auditar o fechamento da Wave 5.

**Próximo passo:** se/quando GO → **W6-C19 · Camada Transversal de Animações** (abre a Wave 6); enquanto NO-GO → as remediações acima (começando pela auditoria do C17).

**Definition of Done:** N/A (auditoria) — entregue: relatório `AUDITORIA-WAVE-5.md`, logs de evidência, entrada no SESSION_LOG. Nenhuma mudança de produção, CHANGELOG ou DECISIONS.

---

## Sessão 23 — 2026-06-18 — [Wave 5 / Componente C17] Relatórios — reconstrução visual fiel ao design (sessão de design)

**Objetivo:** Alinhar a UI dos Relatórios ao **Figma**, aba por aba (as fórmulas/métricas já estavam corretas desde a Sessão 22). Trabalho conduzido de forma **iterativa com o dono**: para cada parte, ele enviava a referência do design + um print do estado atual e pedia fidelidade simétrica.

**Feito (ordem do trabalho):**
- **Cabeçalho/filtros:** gap **constante** + campos que **crescem** para preencher (sem buraco — o dono distribuiu as larguras, não os espaços); tab bar e toggle de rota com **pílula deslizante** (`layoutId`, como no C09); **campo de data como trigger** (ícone à direita, clique no box abre o calendário, estilo personalizado); **chip de período removido**; `Dropdown` ganhou **variante `branco`** (respiro lateral nas opções) + **scrollbar fino** no painel.
- **Aba Geral → bento (grid 12 col):** Total geral (preto + `VolumeBars`) · Tempo médio · Taxa · Rota (lista ao rodapé) · donut Provas Ativas · ranking tempo-por-vendedor com **progressbar** · Vendedor com mais artes · tabelas Métricas/Atrasadas. Ajustes finos: largura do card Rota, **alinhamento numérico** das tabelas, donut com **anel preto mais fino** (espessura radial por **dois `<Pie>`**), barras mais densas (**binning** + `minPointSize`).
- **Aba 3Studio → bento:** Provas Criadas (preto + gráfico) · Reinícios · Devolvidas · Canceladas (**vermelho**) · Reprov. aguardando (**vermelho**) · Tempo até 1ª mov · **Top motivos** com barras vermelhas + contagem.
- **Aba Vendedores → bento:** Provas Criadas (preto + gráfico) · Ranking por volume (largo, rank-list) · Detalhamento full-width (Vendedor · Local · Aprovação verde · Reprovação vermelho · Tempo · Atrasadas). **Removido** o card "Vendedores Filial" (ausente no design).
- **Backend (aditivo):** as agregações de **3Studio** e **Vendedores** ganharam **`provas_criadas` + a série `volume`** (reuso da query de volume da Geral) para o card "Provas Criadas"; refletido nos `*Out` e nos tipos TS.

**Decisões (ADRs):**
- **ADR-094** — reconstrução visual fiel ao design (bento por aba) + contrato de `volume` nas abas 3Studio/Vendedores. Aceita; iterada e aprovada pelo dono aba a aba.

**Testes / cobertura:**
- api: `test_relatorios.py` + `test_relatorios_endpoints.py` **29 verdes @db** (PG local 5432, cluster `.tmp-pg`); `mypy --strict` limpo. *(Correção da Sessão 25: `ruff format` NÃO estava limpo — ficou dívida no repo, fechada na remediação da Wave 5.)*
- web: `pnpm test` (relatórios) verde; `lint`/`build` limpos. *(Correção da Sessão 25: `prettier` deixou um arquivo local com whitespace — corrigido na remediação.)*

**Pendências / em aberto:**
- [x] **Aba Clicheria** — reconstruída em bento no commit `9e3fbde` (fecha a fidelidade visual do C17).
- [ ] Avaliar se "Provas Criadas" é o melhor rótulo do card preto na aba Vendedores (seguiu a imagem do design; o dono pode redefinir).

**Próximo passo:**
- *(Atualizado na Sessão 25)* **W5-C18 foi CORTADO por decisão de produto (ADR-095)** — a Wave 5 entrega só o C17. Próximo: re-auditar a Wave 5; se GO → **W6-C19**.

**Definition of Done:** ⚠️ parcial — refino de UI sobre o C17 já entregue (Sessão 22): testes/lint/build/prettier verdes, sem migration nova; a fidelidade visual fecha quando a aba Clicheria for reconstruída.

---

## Sessão 22 — 2026-06-17 — [Wave 5 / Componente C17] Relatórios Gerenciais (4 abas) — **abre a Wave 5**

**Objetivo:** Entregar a seção de relatórios gerenciais **exclusiva do 3Studio**, **fiel ao design** (abas Geral / 3Studio / Vendedores / Clicheria, filtros compartilhados, gráficos, tabelas, **export CSV**), reusando a função de horas úteis e o padrão de agregação do C16, com a distribuição por rota somando 100% e o CSV preservando os campos exibidos.

**Feito:**
- **Scout (workflow, 7 agentes) + leitura do RequisitosProvasDigitais_v1_0.docx** ANTES de decidir: aterrou C16 (`atraso_sql`/`instante_limite_atraso`/`dashboard_repository`), C11 (`movimentacoes`), C07 (filtros/URL-state), C09 (delay), RBAC, e o §7 (Relatórios = "Exclusivo 3Studio" → flag admin). Resolveu drifts do prompt (Recharts NÃO instalado; `Recurso.RELATORIOS` JÁ existia; toggle de rota 2-vias × 4 rotas; delay lido inline; motivo em `movimentacoes.motivo`).
- **Pontos de Decisão (§4) apresentados em bloco e respondidos pelo dono** (2 rodadas de AskUserQuestion) ANTES de codificar.
- **Backend:** migration **`0021`** `private.horas_uteis_entre(inicio, fim)` (+ espelho RLS); `domain/relatorios.py` (fórmulas DP-3 — fonte única); `application/ports/relatorios_repository.py`; `adapters/outbound/db/relatorios_repository.py` (4 agregações SET-BASED, sem N+1, reusando os fragmentos de atraso do C16 verbatim); `application/relatorios.py` (serviço + **CSV** UTF-8 BOM+`;`); `adapters/inbound/http/relatorios.py` (4 endpoints por aba + `/exportar` + filtros compartilhados); `get_relatorios_service` (gate `RELATORIOS` → 403) + router em `app.py`.
- **Frontend:** `lib/api/relatorios.ts` (tipos + fetch por aba + download CSV), `lib/relatorios/format.ts`; `/relatorios` (`page.tsx` Suspense, `error.tsx`, `relatorios.module.css`) + `_components/` (view com tab bar + filtros + Exportar CSV caret, 4 tabs lazy, `charts.tsx` Recharts barras+donut, `widgets.tsx` StatCard/ListaBarra, `use-relatorio.tsx` hook stale-safe). **Recharts adicionado** (`recharts@3.8.1`).
- **Migration `0021` aplicada no Supabase real** via MCP (`apply_migration` + bump `alembic_version=0021`); função verificada (2h dentro da janela, 2h cruzando o fim de semana).

**Decisões (ADRs):**
- ADR-086 sequenciamento (4 abas numa sessão) · ADR-087 conjunto de métricas (segue o design) · **ADR-088 fórmulas (DP-3 — a mais importante)** · ADR-089 CSV server-side UTF-8 BOM+`;` · ADR-090 agregação lazy sem Realtime + `horas_uteis_entre` · ADR-091 filtros/população por `created_at`/nº requerimento · ADR-092 Recharts (corrige drift do prompt/CLAUDE.md §4) · ADR-093 acesso flag admin (recurso já existia).

**Testes / cobertura:**
- api: **807 verdes** (offline + `@db`, PG local 5432) — `test_relatorios.py` (CSV/BOM/campos/acentuação, `_taxa`, `dias_no_periodo`, zero-fill rotas), `test_relatorios_endpoints.py` (`private.horas_uteis_entre` parametrizado; 4 abas com fórmulas conferidas; **distribuição soma 100%**; **atrasadas = regra do C16**; filtros rota-multi/vendedor/status/período; **403 não-admin** em todas as abas + export; **CSV** BOM/campos/filtros), `test_migrations.py` (head **0021** + cria/remove `horas_uteis_entre`). `ruff`/`mypy --strict` limpos.
- web: **178 verdes** (`relatorios-view.test.tsx`: shell + 4 abas + Exportar CSV; **lazy** — só a aba ativa busca; troca de aba → `?aba=`; export dispara download; preset escreve De/Até). `lint`/`build`/`prettier` limpos.

**Pendências / em aberto:**
- [ ] **Dívida pré-existente de lint (NÃO do C17):** `ruff check .` acusa **E501** em 2 arquivos de teste do W4 (`tests/integration/test_dashboard_endpoints.py`, `test_provas_listagem_atrasada_endpoints.py`) + 1 `set-state-in-effect` — chips de tarefa de limpeza sugeridos. Meus arquivos novos estão 100% limpos.
- [ ] **Operação (push em tempo real não se aplica aqui — relatórios são snapshot):** nada novo. O role de runtime e as 4 `R2_*` seguem como pendências de operação herdadas.

**Próximo passo:**
- **W5-C18 — Atalhos rápidos** (RF-017): seção de atalhos role-aware (escanear / provas / relatórios). Comando: cole o prompt do C18 com os docs de contexto + Wave 4/C16 e C17 mergeados.

**Definition of Done:** ✅ atendida — code review (multi-agente recomendado), testes ≥ alvo, migration versionada/aplicada/round-trip, critérios §6 demonstrados (acesso 3Studio, soma 100%, CSV preserva campos, consistência com o C16), sem Realtime, `prefers-reduced-motion`, sem segredos, docs (`docs/relatorios.md`).

---

## Sessão 21 — 2026-06-17 — [Wave 4 / Componente C16] Dashboard com Contadores em Tempo Real — **abre a Wave 4**

**Objetivo:** Entregar o dashboard de visibilidade operacional **fiel ao design** (layout bento), com contadores em tempo real, clicáveis, escopados por perfil (RLS), via **uma única** subscription Realtime e **uma única** consulta de agregação — reconciliando o design com o RF-015.

**Feito:**
- **Pontos de Decisão (§4) apresentados em bloco e respondidos pelo dono** (AskUserQuestion) ANTES de codificar.
- **Backend (consulta única — RNF-022, mínimo de requisições):** `domain/dashboard.py` (DTOs + mapeamento contador→status DP-2 + janela comercial de referência); `application/ports/dashboard_repository.py` + `adapters/outbound/db/dashboard_repository.py` (UMA query SQL retornando os 5 contadores + breakdown de "Atrasadas" por vendedor/total, lendo o delay do C09 inline e chamando `private.instante_limite_atraso`/`private.nomes_de_vendedores` na mesma ida); `application/dashboard.py` (serviço fino); `adapters/inbound/http/dashboard.py` (`GET /dashboard`); `get_dashboard_service` (gate `DASHBOARD` universal, sessão RLS) + router em `app.py`.
- **Migration `0020`** — `private.instante_limite_atraso(timestamptz, integer)` (horas úteis seg–sex 07–18, fuso America/São_Paulo, instante-limite por monotonicidade; schema `private` não exposto; `STABLE`/`SECURITY INVOKER`/`search_path=''`) + grant + espelho `migrations/rls/instante_limite_atraso.sql`. `upgrade`/`downgrade` testados.
- **Shared SQL** `adapters/outbound/db/atraso_sql.py` (predicado "atrasada" — fonte única; terminais derivados de `ESTADOS_TERMINAIS`).
- **C07 estendido (DP-6, sem regressão):** `FiltrosProvas.status` virou tupla (multi-valor → `IN`) + `atrasada`; endpoint aceita `status` repetido + `atrasada`; repo aplica os filtros. Front: `listarProvas` envia múltiplos `status`/`atrasada`; `provas-view` lê `getAll("status")` + `atrasada` + chip "Atrasadas ✕".
- **Frontend:** `components/ui/animated-counter/AnimatedCounter.tsx` (count-up RF-025, reduced-motion); `lib/api/dashboard.ts` + `fetchDashboard` server (SSR) em `lib/api/server.ts`; `app/(app)/dashboard/page.tsx` (perfil + carga SSR) + `_components/dashboard-view.tsx` (bento, cards clicáveis, Atrasadas lista+total, atalhos role-aware, **UMA** subscription Realtime → refetch único debounced, degradação graciosa) + `dashboard.module.css` + tokens `--dash-*` em `globals.css`.
- `docs/dashboard.md` (conjunto reconciliado, agregação única, cálculo de atraso, breakdown, Realtime, escopo, navegação, checklist §6).

**Decisões (ADRs):** ADR-080 (DP-1: design exato, desvio consciente do RF-015 — §2.1) · ADR-081 (DP-2: mapeamento contador→status, "Na clicheria"=`recebida_clicheria`) · ADR-082 (DP-3: atalhos role-aware) · ADR-083 (DP-4: "Atrasadas" por vendedor + horas úteis via instante-limite único, sem polling) · ADR-084 (DP-5: Realtime único + agregação única RLS-escopada / mínimo de requisições) · ADR-085 (DP-6: bento sem Recharts + count-up + C07 multi-status/`atrasada`).

**Testes / cobertura:**
- Backend (@db, Postgres real `.tmp-pg` na 5432): `test_dashboard.py` (unit: serviço + mapeamento DP-2), `test_dashboard_endpoints.py` (função de horas úteis — 5 casos noite/fim de semana; escopo por perfil studio/admin/vendedor/motorista; breakdown ordenado; última movimentação ≠ created_at; terminal excluído; **sem N+1**; 401/403), `test_provas_listagem_atrasada_endpoints.py` (multi-status `IN`, status único intacto, `atrasada`, combinação). `test_migrations.py` atualizado (head `0020` + função no `private` no upgrade, removida no downgrade). **Suíte completa: 778 testes verdes** (`ruff`/`mypy --strict` limpos).
- Frontend: `dashboard-view.test.tsx` (render fiel, count-up, **uma** subscription + cleanup, evento → refetch único debounced + update, degradação graciosa, cliques → deep-links, atalho Nova Prova oculto p/ não-3Studio, carga sem SSR). **173 testes verdes** (`pnpm lint`/`build`/`format:check` limpos). **C07 sem regressão.**

**Pendências / em aberto:**
- [ ] **Operação (push em tempo real):** habilitar a replicação da tabela `provas` no painel do Supabase (Database → Replication / `supabase_realtime`) — sem isso o painel funciona com a carga SSR, só não recebe push automático.
- [ ] (latente, fora de escopo) — o `prettier --check` da Wave anterior estava com um arquivo de teste do C08 dessincronizado; reformatado nesta sessão para manter `format:check` verde.

**Próximo passo:**
- **W5-C17 — Relatórios Gerenciais com Distribuição por Rota** (abre a Wave 5): tempo médio por etapa, taxa de reprovação, distribuição por rota, export CSV (agregações analíticas sobre `provas`/`movimentacoes`). Comando: cole o prompt do C17 com os docs de contexto + Waves 0–4.

**Definition of Done:** ✅ atendida — code review interno, testes (escopo por perfil, sem N+1, horas úteis, breakdown), migration versionada/`upgrade`+`downgrade`, sem polling (RNF-021), agregação única (RNF-022), count-up com `prefers-reduced-motion`, sem segredos versionados, docs do módulo, **migration `0020` aplicada no Supabase real**.

---

## Sessão 20 — 2026-06-17 — [Wave 3 / Remediação] Fechamento dos achados da auditoria da Wave 3

**Objetivo:** Sessão de **remediação dirigida pelo relatório** `docs/audits/AUDITORIA-WAVE-3.md` (veredito GO, 0 Críticos/0 Altos). Fechar os 3 Médios + os Baixos endereçáveis, cada correção blindada por teste de regressão, sem abrir novo buraco (nenhum caminho de status fora do motor, sem perda de atomicidade/idempotência, sem enfraquecer RLS/anti-enumeração). Re-auditável ao final.

**Ponto de decisão (apresentado ao dono, §4 do prompt):** como o escopo mandatório (Críticos/Altos) estava vazio, perguntei a **profundidade do M-01** e o tratamento dos Baixos. Dono escolheu **"Operational hardening"** (docs + checagem de boot; **sem `FORCE RLS`**) e **"Fix all addressable Lows"**. Registrado em ADR-079.

**Feito (causa raiz, um teste por achado):**
- **M-01** ✅ — `.env.example`/`docs/rbac.md`/`docs/provas.md` exigem `rastreio_runtime` (NOBYPASSRLS) em staging/produção; nova `verificar_role_runtime_nao_privilegiado` (`infrastructure/database.py` → `lifespan`) **recusa boot** com role superuser/BYPASSRLS em deploy (no-op dev/test; degrada se banco fora do ar). **`FORCE RLS` NÃO** (superuser o ignora; quebraria os `private.*`). Testes: `test_database_offline.py::TestChecagemDeRolePrivilegiado` + `test_database.py` (@db).
- **M-02** ✅ — migration **`0019`** (`CREATE OR REPLACE private.nomes_de_vendedores` com 6 estados = `ESTADOS_ESCOPO_MOTORISTA`) + espelho; teste de equivalência do Motorista ganhou a 5ª fonte (a lacuna do drift) + asserção de `prosrc`.
- **M-03** ✅ — novo `tests/unit/test_equivalencia_rls_wave3.py` (nomes + grants append-only + corpo) p/ `movimentacoes`/`assinaturas`/`rate_limit_contadores`.
- **L-02/L-03/L-04** ✅ — token `--motion-pulse`; remoção das transições `background/color` dos botões admin; remoção da diretiva ESLint ociosa + `aria-invalid` no `button` do `Dropdown`.
- **Processo** — `pyproject.toml` `extend-exclude=["audit"]` no ruff: os scripts descartáveis da auditoria estavam commitados *lint-dirty* (o "ruff clean" do relatório era pré-commit deles); alinhado ao escopo de `mypy`/`pytest`. `ruff check .` volta a 0.
- **L-01/L-05** mantidos (aceites documentados — ADR-065 / ADR-063·RN-014; não-defeitos).
- Relatório `AUDITORIA-WAVE-3.md` atualizado: "Status da remediação" no §1 + linha **✅ Resolvido**/**Mantido** por achado + conclusão recomendando re-auditoria.

**Decisões (ADRs):**
- **ADR-079** — Remediação da Wave 3: endurecimento operacional do role de runtime (M-01) sem `FORCE RLS`; alinhar (não documentar) o resolvedor (M-02); estender o harness (M-03); excluir `audit/` do ruff. **Aceita.**

**Testes / cobertura:**
- api: `pytest --cov` **758 passed / 94.07%** (motor `machine.py`/`rules.py`/`enums.py` **100%**, `transicoes.py` 99%) — **+22 testes de regressão** vs. os 736 do baseline, **zero regressão**. `ruff check .` **0**, `mypy --strict` **Success (85 arquivos)**.
- migration `0019` up/down limpa (`test_migrations.py`, head `0019`).
- web: `pnpm lint` **0 warnings**, `build` OK, `pnpm test` **165 passed**.

**Pendências / em aberto:**
- [x] **Migration `0019` aplicada no Supabase real** (`rastreio-provas-digitais`, `wmpxxrzbzqgsorjwczvz`) via MCP — `alembic_version=0019`, `private.nomes_de_vendedores` com as origens, ainda fora do schema exposto. **Advisors de segurança sem achados novos** (só os 2 pré-existentes: RLS-no-policy do `alembic_version` lockado e leaked-password).
- [ ] **Re-auditar a Wave 3** (head `0019`) — a palavra final do GO é da auditoria, não da remediação.

**Próximo passo:**
- **Re-auditar a Wave 3**; se confirmar GO, seguir para **W4-C16 — Dashboard Realtime**.

**Definition of Done:** ✅ atendida — todos os Médios/Baixos endereçáveis resolvidos com teste de regressão; suíte verde sem regressão (ruff/mypy/pytest+cobertura, web lint/build/test); migration `0019` up/down e RLS reaplicáveis; sem segredos versionados; nenhuma correção abriu novo buraco.

---

## Sessão 19 — 2026-06-17 — [Wave 3 / Auditoria] Auditoria adversarial da Wave 3 (C10–C15) — **read-only**

**Objetivo:** Auditoria independente e adversarial da Wave 3 inteira (Movimentação: C10 Escaneamento, C11 Máquina de Estados, C12 Assinatura, C13 Timeline, C14 Cancelamento, C15 Reinício) — verificar empiricamente a integridade do estado das provas e emitir veredito Go/No-Go. **Sessão read-only: nenhum código de produção foi alterado.**

**Veredito:** ✅ **GO** — **0 Críticos, 0 Altos**, 3 Médios, 5 Baixos (todos dívida não-bloqueante). Relatório completo em `docs/audits/AUDITORIA-WAVE-3.md`.

**Feito (executar, não confiar):**
- Linha de base verde: `pytest --cov` **736 passed / 94.02%** com o **motor a 100%** (`machine.py`/`rules.py`/`enums.py` 100%, `transicoes.py` 99%); `ruff` + `mypy strict` limpos (84 arquivos); web `pnpm lint` (0 err) + `build` + `test` (165 passed).
- Fan-out de 5 auditores estáticos read-only (motor vs §6, status-writes, RLS, frontend, docs/migrations).
- Testes de auditoria descartáveis em `apps/api/audit/` (temporários): `run_audit.py` (concorrência C4, terminais A3, cancelar-de-terminal G1/RN-005 → **5/5 PASS**) e `introspect_rls.py` (roles/FORCE-RLS/triggers/grants).
- Cross-check célula a célula da §6 (4 rotas) e §7 (extraídas do `RequisitosProvasDigitais_v1_0.docx`).

**Achados (sem correção — para a remediação):**
- 🟡 M-01 (F2): nenhuma tabela usa `FORCE ROW LEVEL SECURITY` e `.env.example` aponta o runtime ao owner. **Rebaixado de Crítico→Médio** pela verificação empírica: o caminho de request força a RLS via `SET LOCAL ROLE authenticated` por transação (fail-closed, `database.py:195-199` + `main.py:68`) — isolamento provado mesmo conectado como `postgres` superuser. Endurecimento operacional (usar `rastreio_runtime`), não vazamento demonstrado.
- 🟡 M-02 (F): drift do resolvedor `private.nomes_de_vendedores` (escopo Motorista estreito vs RLS ampliada do C11) — restritivo, cosmético (nome em branco), não-leaking.
- 🟡 M-03 (I2): espelhos RLS de `movimentacoes`/`assinaturas`/`rate_limit` sem teste de equivalência (só `provas_*`/`system_settings` têm).
- ⚪ L-01..L-05: scope de leitura do Motorista route-blind (ADR-065); literal `1600ms` no pulso do timeline; transição CSS de `background/color` nos botões admin; 2 warnings ESLint; 403-vs-404 do perfil-errado-em-escopo (RN-014, não-explorável).

**Decisões (ADRs):** Nenhuma (sessão de auditoria — sem mudança de arquitetura; `DECISIONS.md`/`CHANGELOG.md` não alterados por não haver correção).

**Pendências / em aberto:**
- [ ] Remediação leve da Wave 3 (M-01/M-02/M-03) — não-bloqueante; idealmente endurecer o role de runtime (M-01) antes do 1º deploy de produção.
- [ ] Os scripts `apps/api/audit/` são descartáveis — remover na remediação se não forem promovidos a testes.

**Próximo passo:**
- **GO** → seguir o roadmap: **W4-C16 · Dashboard Realtime**. (A remediação dos Médios pode correr em paralelo, quando conveniente.)

**Definition of Done:** N/A (sessão de auditoria read-only; nenhum componente de código fechado).

---

## Sessão 18 — 2026-06-17 — [Wave 3 / Componente C15] Reinício de Ciclo (Reprovação) — **fecha a Wave 3**

**Objetivo:** Entregar a **ação administrativa de reiniciar o ciclo** de uma prova reprovada — disponível ao 3Studio **só em "Reprovada pelo Vendedor"**, **invocando o motor do C11** (→ `criada`), **incrementando `ciclo_atual` na mesma transação atômica**, preservando rota e histórico, **sem assinatura e sem motivo** (§6.6 — só confirmação).

**Feito:**
- **Grounding (régua PARE E PERGUNTE):** workflow de 7 leitores paralelos sobre o motor do C11 (`rules.py`/`machine.py`/`enums.py`/`transicoes.py`), o cancelamento do C14 (molde), schema de `movimentacoes`/grants, RBAC, a timeline do C13 e o slot do botão no C08 — corroborado por leituras diretas dos arquivos decisivos. **Achados que encolheram o C15:** (1) a aresta `_REINICIAR` (`reprovada_vendedor → criada`, ADMIN) **já existia em todas as 4 rotas**; (2) `Recurso.REINICIAR_CICLO` **já existia** nos 3 espelhos RBAC (admin-only); (3) o motor **já carimbava** `movimentacoes.ciclo` — DP-3 **sem retroação**; (4) o motor **deliberadamente não** mexia em `ciclo_atual`. **Bloqueador descoberto:** o GRANT de UPDATE de `provas` a `authenticated` é de **coluna** (3 colunas) e **não** incluía `ciclo_atual` → o incremento falharia com *"permission denied for column"* no role NOBYPASSRLS. Apresentei os 5 Pontos de Decisão e **aguardei** as respostas.
- **Decisões do dono (DP-1..5):** Pré-incremento (a movimentação de reinício fecha o ciclo N); **sem motivo** (só confirmação); botão **construtivo** (não-perigo); seguir o padrão C04/C08 (sem Figma).
- **Backend:** `incrementa_ciclo(acao)` + `ACOES_REINICIO` (domínio, fonte única); `ProvasRepositoryPort.incrementar_ciclo` (UPDATE atômico `ciclo_atual+1 RETURNING`); `executar` chama o incremento na mesma transação **depois** de registrar a movimentação (carimbo pré-incremento) e reflete o novo ciclo no resultado; **migration `0018`** (GRANT `UPDATE(ciclo_atual)` + mirror `provas_grants.sql` com as 4 colunas); `get_reinicio_service` (gate `REINICIAR_CICLO`) + endpoint dedicado **`POST /provas/{id}/reiniciar`** (`ReiniciarIn{idempotency_key}`).
- **Frontend:** `reiniciarCiclo` (`lib/api/transicoes.ts`); `podeReiniciar` resolvido no servidor (`page.tsx`, mesmo `fetchUsuarioAtual`); botão `.btnReiniciar` (construtivo) no `.acoes`, gated `podeReiniciar && status === "reprovada_vendedor"`; `ReiniciarCicloModal` (sem motivo) reusando `MotionModal`; sucesso reflete "Criada" + ciclo da resposta e recarrega a timeline.
- **Deploy:** migration `0018` **aplicada no Supabase real** (`alembic_version=0018`; grant de `provas` agora `ciclo_atual, finalizada_em, status, updated_at`; advisors **sem achados novos** — só os 2 pré-existentes).

**Decisões (ADRs):**
- **ADR-076:** reiniciar via o motor do C11 + incremento atômico de `ciclo_atual`, endpoint dedicado + 2 camadas + GRANT 0018 (DP-1).
- **ADR-077:** reinício sem assinatura nem motivo — só confirmação (DP-2).
- **ADR-078:** carimbo de ciclo pré-incremento + UX construtiva/gating server-side (DP-3·DP-4·DP-5).

**Testes / cobertura:**
- api: `test_state_machine.py` (+`incrementa_ciclo` e derivação travada), `test_transicao_service.py` (+incremento/idempotência/carimbo/estado inválido), **`test_reinicio_endpoints.py`** (@db: feliz/rota+histórico preservados/estados inválidos/403 borda/401/idempotência sem reincrementar/Vendedor-admin/404), `test_migrations.py` (head `0018` + asserção do grant). **735 verdes, 94,0%** (machine.py 100%, transicoes.py 99%, rules.py 100%) — `ruff`/`mypy --strict` limpos.
- web: `prova-detalhe-view.test.tsx` (+4 casos de reinício). **165 verdes**; `lint`/`build` limpos (2 warnings pré-existentes alheios).

**Pendências / em aberto:**
- [ ] **Auditoria da Wave 3** (como nas waves anteriores) antes de iniciar a Wave 4 — Wave 3 (C10–C15) está completa.
- [ ] Pendências de responsável herdadas (não-bloqueantes do C15): habilitar o hook de claims no dashboard, cadastrar `SUPABASE_SECRET_KEY`/`KEEPALIVE_DATABASE_URL`, política de senha, ativar o role `rastreio_runtime` (LOGIN/senha) em produção.

**Próximo passo:**
- **W4-C16 · Dashboard com Contadores em Tempo Real** (abre a Wave 4) — sugerida a **auditoria da Wave 3** antes.

**Definition of Done:** ✅ atendida — code review (revisão própria + workflow de grounding), testes ≥80% domínio/serviço e **≥95% na máquina de estados (100%)**, integração @db verde, migration `0018` versionada/documentada/aplicada (upgrade+downgrade limpos), validada contra os critérios §6 e a Matriz §7 (acesso não-3Studio bloqueado em 2 camadas), sem erros de console/logs críticos, docs do módulo (`docs/reinicio-ciclo.md`), animação do modal com `prefers-reduced-motion`, idempotência verificada (sem duplo-incremento), sem segredos versionados.

---

## Sessão 17 — 2026-06-17 — [Wave 3 / Componente C14] Cancelamento de Prova Digital

**Objetivo:** Entregar a **ação administrativa de cancelar** uma prova — disponível ao 3Studio em qualquer estado ativo, com motivo obrigatório, **invocando o motor do C11** (→ `cancelada`), terminal e irreversível (RN-005), preservando o histórico.

**Feito:**
- **Grounding (régua PARE E PERGUNTE):** workflow de 6 leitores paralelos sobre o motor do C11 (`rules.py`/`machine.py`/`enums.py`), serviço/endpoint de transição, RLS de `movimentacoes`/`assinaturas`, RBAC e o slot do botão no C08 — corroborado contra os ADRs (ADR-061/062/064/065/066/067). Três achados decisivos: (1) o C12 tornou a **assinatura obrigatória em TODAS as ações** (logo um cancelamento sem traço seria barrado — §6.6 manda o contrário); (2) cancelar tinha **uma só camada de enforcement** (o motor — o `/transicoes` é gate universal `ESCANEAR`; `Recurso.CANCELAR_PROVA` existia mas não estava ligado); (3) o hook **`useAuthorization` não existe** (drift do prompt). Apresentei os 5 Pontos de Decisão e **aguardei** as respostas.
- **Backend — assinatura opcional p/ administrativas (ADR-074):** `exige_assinatura(acao)` + `ACOES_ADMINISTRATIVAS = {CANCELAR, REINICIAR_CICLO}` em `machine.py` (derivado das transições `ADMIN` — teste de consistência); `executar` aceita `assinatura_imagem: bytes | None` → cancelar grava `assinatura_ref` NULL (coluna já nullable — ADR-066, **sem migration**). Guarda: operacional com `None` → 422.
- **Backend — endpoint dedicado (ADR-073):** `POST /provas/{id}/cancelar` (`CancelarIn{motivo, idempotency_key}`) + `get_cancelamento_service` gateado por `Recurso.CANCELAR_PROVA` (borda) chamando o MESMO motor → **2 camadas reais** (borda + motor). Fonte de status única (ADR-062). `/transicoes` intacto.
- **Frontend (ADR-075):** `page.tsx` resolve `podeCancelar = can(perfil, "cancelar_prova")` no servidor e passa ao view; botão de perigo só em estados ativos; `CancelarProvaModal` (reusa `<MotionModal>`) com motivo obrigatório + aviso de irreversibilidade; **remontagem por `key`** (idempotência no `useState` initializer, sem `setState` em efeito); sucesso reflete `Cancelada` + recarrega a timeline (`recarregar` na `<ProofTimeline>`).
- **Refino de layout (a pedido do dono, pós-entrega):** o "Cancelar prova" entrou na **mesma linha das ações de etiqueta** — `.acoes` virou **flex de larguras iguais** (2 botões → 50/50; com o cancelar → **3 botões a 1/3**: Visualizar · Baixar · Cancelar), removendo o bloco `.acoesPerigo` separado. Commit `style(w3-c14)`.
- **Verificações executáveis** contra o cluster `.tmp-pg` local (PG 17, porta 5432 nesta sessão; `alembic_version=0017`).

**Decisões (ADRs):**
- ADR-073: cancelar via o motor do C11, por endpoint dedicado `POST /provas/{id}/cancelar` com gate de borda `CANCELAR_PROVA` (2 camadas) — DP-1/DP-4.
- ADR-074: cancelamento **sem assinatura desenhada**; assinatura opcional para `ACOES_ADMINISTRATIVAS` — DP-2 (resolução RN-003 × §6.6).
- ADR-075: UX destrutiva (gating server-side por `podeCancelar`, modal remontado por `key`, sem `useAuthorization` inexistente) — DP-3/DP-5.

**Testes / cobertura:**
- **api: 714 verdes (offline + @db), cobertura 94,2% — `machine.py` 100%, `transicoes.py` 99%**. Novos/estendidos: `test_state_machine.py` (consistência `ACOES_ADMINISTRATIVAS`/`exige_assinatura`), `test_transicao_service.py` (cancelar sem assinatura → `assinatura_ref` NULL; operacional sem assinatura → 422), **`test_cancelamento_endpoints.py`** (16 casos @db: caminho feliz sem assinatura, motivo obrigatório front/back, terminal → 422, não-admin → 403 na borda, irreversibilidade, idempotência, admin vê tudo, inexistente → 404).
- **web: 161 verdes.** `prova-detalhe-view.test.tsx` (gating por perfil + estado, modal exige motivo, reflete Cancelada + recarrega timeline, erro de regra → toast); E2E `e2e/cancelamento.spec.ts` (gated `E2E_LIVE`/`E2E_CANCELAR`). `lint`/`build`/`prettier` limpos.

**Pendências / em aberto:**
- [ ] **Sem migration nova** — nada a aplicar no Supabase real (head segue `0017`); a coluna `movimentacoes.assinatura_ref` já era nullable.
- [ ] Operação (herdada): cadastrar `KEEPALIVE_DATABASE_URL` (W0-A-001); ativar role de runtime/`R2_*` quando for a produção.

**Próximo passo:**
- **W3-C15 — Reinício de Ciclo (Reprovação):** UI/gatilho de Reiniciar (admin) que invoca o motor do C11 (`reprovada_vendedor → criada`) **e incrementa `prova.ciclo_atual`**; herda o molde do C14 (endpoint dedicado + gate `REINICIAR_CICLO`; `REINICIAR_CICLO ∈ ACOES_ADMINISTRATIVAS` já sem assinatura). Carimbo do ciclo conforme ADR-071.

**Definition of Done:** ✅ atendida — code review (revisão própria), testes ≥ DoD (máquina 100% ≥ 95%; serviço/domínio altos ≥ 80%), acesso não-3Studio bloqueado em 2 camadas, sem motivo bloqueado, irreversibilidade demonstrada, sem erro de console/log crítico, docs do módulo, modal com `prefers-reduced-motion`, sem segredos versionados, sem N+1, idempotência verificada.

---

## Sessão 16 — 2026-06-16 — [Wave 3 / Componente C13] Timeline Visual com 4 Rotas e Laminação

**Objetivo:** Preencher a seção "Histórico de movimentações" do detalhe (C08), em empty state, com a **timeline visual** `<ProofTimeline>` — renderização adaptativa por rota, etapa atual destacada (animada), laminação/contexto de motorista diferenciados, reprovação com motivo, múltiplos ciclos com separador — lendo `movimentacoes` (C11) com respeito à RLS.

**Feito:**
- **Grounding (régua PARE E PERGUNTE):** workflow de 6 leitores paralelos sobre C11/C12/C08/C07 + verificação direta. Resolvi um **conflito entre agentes**: a coluna **`movimentacoes.ciclo` EXISTE** (models.py:216, carimbada em `transicoes.py:171`) — a doc/ADRs do C11 não a mencionavam (drift de doc; o código vence). Isso tornou o **DP-3 sem retroação**.
- **Pontos de Decisão (§4) ao dono, respostas:** DP-1 = **derivar no backend**; DP-2 = **endpoint dedicado**; DP-2b = **resolver nome pessoal** (migration); DP-2c = **sem visualizador de assinatura** (só selo); DP-5 = **seguir o padrão do C08**. DP-3 = usar `movimentacoes.ciclo`; DP-4 = caminho completo desde a criação (recomendação mantida).
- **Backend:** `sequencia_canonica(rota)` + `ACOES_AVANCO` (puro, derivado de `TRANSITION_RULES` — DP-1); `MovimentacoesRepositoryPort.listar_por_prova`/`nomes_de_atores` + impl; `ProvasConsultaService.obter_movimentacoes` (+ `TimelineProva`/`MovimentacaoComAtor`, repo de movs injetado no DI); endpoint **`GET /provas/{id}/movimentacoes`** + schemas `TimelineOut`/`MovimentacaoOut` (`tem_assinatura` = selo). Migration **`0017`** + `migrations/rls/nomes_de_usuarios.sql` (`private.nomes_de_usuarios` SECURITY DEFINER, escopo do chamador re-aplicado).
- **Frontend:** `lib/api/timeline.ts`; `lib/provas/timeline.ts` (`construirTimeline` puro + `ESTADOS_LAMINACAO`/`ESTADOS_MOTORISTA`); `<ProofTimeline>` + CSS Module (vertical, responsivo, revelação progressiva + anel pulsante, `prefers-reduced-motion`); integrado no detalhe substituindo o empty state (classes mortas removidas). Reusa `rotuloStatus` (C07) e `rotuloRota` (C08).
- **Supabase real:** verifiquei o head (estava `0016` — checklist do C12 stale) e **apliquei a `0017`** via MCP — `alembic_version=0017`, `nomes_de_usuarios` em `private` (não em `public`), SECURITY DEFINER, `authenticated` EXECUTE / `anon` não; **advisors sem achados novos** (os 2 pré-existentes permanecem).
- **Correção pós-merge (UI, confirmada pelo dono):** com dados reais, a timeline longa **transbordava para fora do card preto** (etapas caíam no fundo cinza). Causa: `.pagina` do detalhe usava `flex: 1` (prende à altura do viewport e encolhe) → o card `.historico` era comprimido ao `min-height` (320u) e a `<ol>` vazava (overflow visível), sem a página rolar. Fix (só CSS): `.pagina` → `flex: 1 0 auto` (cresce com o conteúdo → rola no `.conteudoInterno`/`overflow-y:auto` do shell) + `.historico` `flex-shrink: 0`. Commit `fix(w3-c13): …`.

**Decisões (ADRs):**
- ADR-069: caminho canônico derivado de `TRANSITION_RULES` (DP-1).
- ADR-070: histórico por endpoint dedicado, não estendendo o detalhe (DP-2).
- ADR-071: agrupamento por `movimentacoes.ciclo` existente, sem retroação (DP-3).
- ADR-072: estados especiais como eventos + nome do ator via `private.nomes_de_usuarios` + assinatura só como selo (DP-4/DP-2b/DP-2c).

**Testes / cobertura:**
- api: `test_state_machine.py` (+`sequencia_canonica` × oráculo independente), `test_provas_timeline.py`, `test_provas_timeline_endpoints.py` (@db), `test_rls_nomes_de_usuarios.py` (@db), `test_migrations.py` (head `0017`). **441 unit + 253 @db verdes**; `ruff`/`mypy --strict` limpos.
- web: `lib/provas/timeline.test.ts` (builder — 4 rotas, statuses, laminação/motorista, reprovação, ciclos), `ProofTimeline.test.tsx`, `prova-detalhe-view.test.tsx` atualizado. **157 verdes**; `lint`/`build` limpos.

**Pendências / em aberto:**
- [ ] **Cancelar (C14) / Reiniciar (C15)** — a timeline já **representa** cancelamento/reprovação/ciclos; as **ações** são C14/C15 (invocam o motor do C11). C15 deve carimbar `reiniciar_ciclo` com o ciclo **pré-incremento** (ver ADR-071).
- [ ] **Dívida de prettier pré-existente (C12):** `confirmar-view.tsx` e `lib/api/transicoes.ts` reprovam `format:check` — não tocados pelo C13; formatados num `style` commit à parte.
- [ ] **Visualizador de assinatura** (imagem por proxy) — fora do escopo do C13 por decisão do dono (DP-2c); pode entrar depois reusando o proxy-streaming do C08.

**Próximo passo:**
- **W3-C14 — Cancelamento de Prova Digital.**

**Definition of Done:** ✅ atendida — code review (revisão adversarial pendente como passo final), testes (4 rotas, ciclos, RLS do histórico, ≥95% na máquina), animações com `prefers-reduced-motion`, sem erro de console/log crítico, docs do módulo (`docs/timeline.md`), migration `0017` versionada/aplicada (up/down limpa), sem segredos versionados.

---

## Sessão 15 — 2026-06-16 — [Wave 3 / Componente C12] Assinatura Digital no Fluxo de Escaneamento

**Objetivo:** Fechar o laço do fluxo de movimentação — tornar *identificar → assinar → confirmar → transição* funcional de ponta a ponta. Assinatura desenhada como comprovante de cada movimentação (RN-003), apresentada automaticamente ao próximo ator (RF-028), capturando e invocando o motor do C11.

**Feito:**
- **Grounding (régua PARE E PERGUNTE):** workflow de 6 leitores paralelos + verificação direta do contrato do C11. Achei **2 premissas erradas no prompt** e as levei ao dono: (1) o C08 **não** tem "padrão de URL pré-assinada" (grep `presigned` = 0 — usa proxy-streaming); (2) `useAuthorization` **não existe** (o RBAC de front é `can`/`podeAcessarRota` em `access-matrix.ts`, e a checagem fina de "é sua vez" é do backend). Confirmados: `movimentacoes.assinatura_ref` nullable sem FK (0015:200), `executar(assinatura_ref)` no ramo `else`, `transicoes_de`+`autoriza` puros, `react-signature-canvas` ausente, head `0015`.
- **Pontos de Decisão (§4) — respostas do dono:** DP-1/DP-2 **bytea em `assinaturas`** (+ FK nullable em `movimentacoes`); atomicidade por **endpoint único** (estende `POST .../transicoes` com a imagem); DP-3 **adicionar `GET /acoes-disponiveis`** reusando o motor; DP-5 resiliência por idempotência+sessionStorage; DP-6 preencher o card de assinatura já fiel ao Figma do C10.
- **Backend:** `domain/assinaturas.py` (`validar_assinatura` magic bytes ≤1 MB); porta + repo `assinaturas`; `AssinaturaRow` + FK em `MovimentacaoRow`; **migration `0016`** (`assinaturas` bytea append-only + RLS + FK do C11) + espelhos `rls/assinaturas_*.sql`; `ProvasTransicaoService` (assinatura+movimentação na MESMA transação; `acoes_disponiveis` filtrando `ACOES_FLUXO_ESCANEAMENTO`); `TransicaoIn.assinatura` (base64) + decode; `GET /acoes-disponiveis`; DI injeta o repo de assinaturas.
- **Frontend:** `lib/api/transicoes.ts`; `_components/assinatura-pad.tsx` (react-signature-canvas 1.1.0-alpha.2 — React 19); `confirmar-view.tsx` reescrito (3 branches DP-4; captura + invoca o C11; resiliência DP-5); `confirmar.module.css` estendido; `error.tsx` (error boundary). Build/lint limpos.
- **`react-signature-canvas`:** `latest` resolveu para **1.1.0-alpha.2** — a linha 1.1 dropou `findDOMNode` (removido no React 19); a stable 1.0.x quebraria. Pinada exata; ships types próprios.

**Decisões (ADRs):** ADR-066 (assinatura bytea na transação + FK), ADR-067 (endpoint único atômico + `acoes-disponiveis` reusando o motor), ADR-068 (resiliência por idempotência + sessionStorage). Ver DECISIONS.md.

**Testes / cobertura:**
- api — `test_assinaturas_dominio.py`; `test_transicao_service.py` reescrito (**vínculo assinatura↔movimentação**, **atomicidade** com falha injetada na assinatura OU na movimentação → nada commitado, idempotência não recria, `acoes_disponiveis`); `test_transicoes_endpoints.py` (assinatura nasce vinculada; **anti-enumeração** acoes/transição; inválida/base64 malformado → 422 sem efeito; reenvio não duplica); `test_rls_assinaturas.py` (SELECT por perfil, INSERT WITH CHECK, append-only); `test_migrations.py` (head `0016`). **671 verdes**, `ruff`/`mypy --strict` limpos.
- web — `confirmar-view.test.tsx` reescrito (3 branches; canvas vazio bloqueia; Reprovar exige motivo; **resiliência preserva o traço + retry com a MESMA chave**; 404). **144 verdes**; E2E `confirmar.spec.ts` (guard + live opt-in RF-028).

**Pendências / em aberto:**
- **Timeline (C13)** — o histórico no detalhe segue em empty state; a RLS de SELECT de `movimentacoes` e de `assinaturas` já está pronta. O **proxy de leitura da imagem** da assinatura é do C13 (define a exibição).
- **Cancelar/Reiniciar (C14/C15)** — invocam o mesmo motor; têm UI própria (fora do fluxo de escaneamento; por isso `acoes-disponiveis` os exclui).
- **Migration `0016` aplicada no Supabase real** (`wmpxxrzbzqgsorjwczvz`) via MCP — `alembic_version=0016`, tabela+trigger+2 policies+FK+RLS verificados, **sem drift**; advisors de segurança **sem achados novos** (os 2 pré-existentes seguem). **O fluxo de movimentação está operacional de ponta a ponta.**

**Próximo passo:** **W3-C13 — Timeline Visual com 4 Rotas e Laminação**.

**Definition of Done:** ✅ atendida — testes (incl. atomicidade assinatura↔transição, anti-enumeração, RLS de `assinaturas`, resiliência/retry), migration `0016` + RLS versionadas/aplicadas, sem erro de console/log crítico, docs (`docs/assinatura.md`), error boundary, animações com `prefers-reduced-motion`, idempotência, sem N+1, sem segredos versionados.

---

## Sessão 14 — 2026-06-16 — [Wave 3 / Componente C11] Máquina de Estados (14 Estados, 4 Rotas) — O CORAÇÃO DO DOMÍNIO

**Objetivo:** O motor de estados autoritativo do sistema — a Requisitos v1.0 §6 inteira como regra **em código** (nunca no banco), um serviço de transição **atômico e idempotente**, a tabela `movimentacoes` **imutável** com RLS, e o endpoint de transição. Predominantemente backend/domínio (sem UI — DP-6). Régua de cuidado no máximo: um erro aqui corrompe silenciosamente o estado de uma prova.

**Feito:**
- **Grounding (régua PARE E PERGUNTE):** extraídos os 3 `.docx` de origem; confrontada a §1.2 do prompt com a **§6 real** dos Requisitos — **idêntica** (revisor adversarial). Mapeado o repo (enum `status_prova_enum` já completo no C06; `Acao` inexistente; helpers RLS reais `app_setor`/`app_is_admin`/`app_current_user_id` — o prompt citava nomes antigos; head `0014`). **Pendência crítica descoberta e levada ao dono:** o Motorista atua a partir de estados de ORIGEM que a RLS (Em Trânsito) não deixava ver → 404 ao escanear. Decisão: ampliar a RLS (ADR-065).
- **Domínio (`domain/state_machine/`):** `enums.py` (`Acao`, `Autorizacao`), `rules.py` (`TRANSITION_RULES` imutável — §6 inteira, `CANCELAR` materializado em todo ativo, `ESTADOS_ESCOPO_MOTORISTA` derivado), `machine.py` (`avaliar_transicao` pura — 422/403/motivo). `domain/movimentacoes.py` (entidade + erro de conflito).
- **Persistência:** migration **`0015`** (`acao_enum` + `movimentacoes` append-only + trigger + RLS + `provas` UPDATE grant/policies + Motorista ampliado), espelhos `migrations/rls/movimentacoes_*.sql`/`provas_update_*.sql`; ORM `MovimentacaoRow`; portas + repos (`obter_para_transicao` FOR UPDATE, `atualizar_status`, `MovimentacoesRepository`).
- **Serviço + borda:** `application/transicoes.py` (lock → idempotência → validação → aplica → commit), `get_transicao_service`, `POST /provas/{id}/transicoes` + `TransicaoIn`, mapeamento de erro (403/409 novos). Round-trip da migration validado (upgrade/downgrade/upgrade) no Postgres local (5433).

**Decisões (ADRs):** ADR-059 (fronteira assinatura C11↔C12 + endpoint no C11), ADR-060 (idempotência: lock pessimista + chave UNIQUE), ADR-061 (`movimentacoes` = log único, **divergência** DAT/Backlog do `audit_log`), ADR-062 (motor completo + split C11/C14/C15 + sem UI), ADR-063 (erros 404/403/422 + anti-enum — DP-7), ADR-064 (Cancelar/Reiniciar pela flag admin), ADR-065 (RLS do Motorista ampliada — **divergência** §7). Detalhes em `DECISIONS.md`.

**Testes / cobertura:**
- **Máquina de estados: 100%** (`enums`/`rules`/`machine`); serviço **98%**; `movimentacoes` domínio 100%. (Adapters de DB ~71-80% — limitação conhecida de cobertura+greenlet do SQLAlchemy async, igual aos repos existentes; o código é exercido pelos @db.)
- **640 testes verdes** (offline + @db no Postgres 5433): `test_state_machine` (118), `test_transicao_service`, `test_transicoes_endpoints` (travessia das 4 rotas, 422/403/404/409, idempotência, Motorista-origem), `test_rls_movimentacoes` (RLS + imutabilidade), equivalência + migrations atualizados.
- **Revisão adversarial multi-agente (regras/concorrência/RLS/superfície): zero achados, todas "ship".** `ruff`/`mypy --strict` limpos.

**Pendências / em aberto:**
- [ ] **Aplicar a migration `0015` no Supabase real** (passo de fechamento — ver resumo da sessão).
- [ ] **Assinatura real** = C12 (substitui o stub de `assinatura_ref` + cria `signatures` + FK).
- [ ] **Timeline** = C13 (lê `movimentacoes`, hoje em empty state no C08).
- [ ] **UI/gatilho de Cancelar (C14) e Reiniciar + incremento de `ciclo_atual` (C15)** — chamam este motor.
- [ ] Role de runtime `rastreio_runtime` (LOGIN/senha) segue passo de operação fora do repo.

**Próximo passo:** **W3-C12 · Assinatura Digital no Fluxo de Escaneamento** — `cd apps/api && uv run uvicorn src.main:app --reload`; ler `prompts/W3-C12-*.md`.

**Definition of Done:** ✅ atendida — cobertura ≥95% na máquina (100%), 403 por perfil + RLS de `movimentacoes` + atomicidade + idempotência testados, migration + RLS versionadas/documentadas, docs do módulo, sem segredos versionados. (Web não tocada — C11 é backend-only.)

---

## Sessão 13 — 2026-06-16 — [Wave 3 / Componente C10] Escaneamento (Câmera + Manual, mobile-first) — ABRE A WAVE 3

**Objetivo:** A ponte física→digital — identificar a prova pela leitura do QR (in-app) ou pela digitação manual, com um endpoint único e idempotente, tudo mobile-first, robusto (câmera negada → manual) e seguro (anti-enumeração + rate limiting). O C10 **só identifica**; transição é C11, assinatura é C12.

**Decisões (respostas dos Pontos de Decisão §4 — confirmadas pelo dono):**
- **DP-1 (bloqueante):** mantido o **formato canônico do C06** `PRV-AAAA-MM-NNNNNN`; a máscara "3S-/8 dígitos" do design é **legado**. Input com prefixo fixo `PRV-` + máscara `AAAA-MM-XXXXXX`; cliente em maiúsculas, **servidor normaliza** (`strip().upper()`) antes de validar. (ADR-052)
- **DP-2:** destino pós-identificação = **uma nova tela de confirmação** (`/provas/[id]/confirmar`) mostrando **nome + requerimento + status** + **placeholder de assinatura** (C12) e "Confirmar movimentação" desabilitado (C11). Não é o detalhe do C08. (ADR-053)
- **DP-3:** rate limiting = **contador Postgres de janela fixa** (`rate_limit_contadores`, 1 linha/ator, upsert atômico, reset por minuto, RLS `self`, sem DELETE); anti-enumeração por reuso do 404 do C08. (ADR-054)
- **DP-4:** lib de câmera = **html5-qrcode** (stack §4); mobile-first de fato (CSS base mobile, safe areas, terço inferior, degradação graciosa). (ADR-055)
- **DP-5:** "Última leitura" = indicador local/sessão; "Ver histórico" = placeholder (C13). (ADR-056)

**Feito:**
- **Grounding (workflow de 5 agentes):** confirmou o formato/regex/charset do C06 (`domain/provas.py`), o QR = código puro, que `resolver_prova()` **não existia** (é do C10), o padrão anti-enum/RLS/DI, a ausência de Redis (só Postgres), e o scaffolding do front (`/escanear` já no nav como placeholder; html5-qrcode **não instalado**).
- **Backend:** `domain/provas.normalizar_codigo` + `LimiteDeTentativasError` (429); `RateLimiterPort` + `SqlAlchemyRateLimiter` (upsert atômico com `app_current_user_id()`); `ProvasRepositoryPort.buscar_por_codigo`; `ProvasIdentificacaoService` (rate limit→commit→normaliza→valida→resolve); `get_identificacao_service` (gate `Recurso.ESCANEAR`); `POST /provas/identificar` (`IdentificarIn`→`ProvaDetalheOut`); `errors.py` mapeia 429; migration **`0014`** (`rate_limit_contadores` + RLS) + espelhos `.sql`; `RateLimitContadorRow` no models.
- **Frontend:** `lib/provas/codigo.ts` (espelho do formato) + `lib/api/escaneamento.ts`; `/escanear` (`EscanearView` + `CameraScanner` com import dinâmico de html5-qrcode + degradação graciosa; `EntradaManual` com máscara; toggle radiogroup; flash de sucesso; rodapé DP-5) + `escanear.module.css` **mobile-first**; `/provas/[id]/confirmar` (view + css). `html5-qrcode ^2.3.8` adicionado.
- **Validação contra Postgres real:** subido o cluster in-repo `.tmp-pg` (PG, porta 5433); corrigido um **desync** (alembic_version=0014 sem a tabela — crash de shutdown do embedded-postgres) via `stamp 0013` + `upgrade head`; ciclo up/down/up do `test_migrations` verde.
- **Revisão adversarial (workflow de 17 agentes, 4 dimensões × verificadores céticos):** 13 achados brutos → **3 confirmados** (1 baixo, 2 médios), corrigidos (ADR-057): anti-enum por comprimento (`IdentificarIn.codigo` `str` puro, comprimento tratado no serviço → mesmo 404, contado no limite); **leak de câmera** em race de unmount-durante-`start()` (`vivoRef` + para o track local na resolução tardia, com teste de regressão); touch target do toggle 42→48px.
- **Refino visual (sessão de design com o dono, mesmo dia — ADR-058):** **Escanear** redesenhada (visor da câmera dimensionado pela altura → nunca estoura; placeholder de QR SVG determinístico + molduras; **scanline animada** via token novo `--motion-scan`; rodapé dentro do card; Manual com input do **código inteiro** sem o `PRV-` fixo via `mascararCodigo`, bloco centralizado, sem outline). **Tela de confirmação** (`/provas/[id]/confirmar`) redesenhada fiel ao Figma (card branco com metadados **justificados** Cliente→Status + card preto "Assinatura Digital" com "Confirmar" = gancho do C11). **Mobile-first** em todas. Vários ciclos de ajuste fino aprovados pelo dono; `web 139 verdes`, lint/build limpos.

**Testes / cobertura:**
- **api: 486 verdes, cobertura 94,55%** (domínio de provas 100%) — unit (`test_provas_identificacao`) + @db (`test_provas_identificacao_endpoints`, `test_rls_rate_limit`, `test_migrations` head 0014). Cobre **idempotência QR/manual** (mesmo registro), **anti-enumeração** (inválido==inexistente==fora-de-escopo, mensagem idêntica), **429** + isolamento por usuário, **RLS do contador**.
- **web: 136 verdes** (`codigo.test.ts`, `escanear-view.test.tsx` — incl. câmera negada→manual e QR==manual mesmo destino, `confirmar-view.test.tsx`) + **E2E** `escanear.spec.ts` (redirect sempre; live opt-in). `ruff`/`mypy --strict`/`lint`/`build`/`format:check` limpos.

**Pendências / em aberto:**
- [x] **Migration `0014` aplicada no Supabase real** via MCP (`rate_limit_contadores` + RLS `self` + grants sem DELETE; `alembic_version=0014`, sem drift; advisors sem achados novos).
- [ ] (Herdadas) segredos `R2_*`/role de runtime/leaked-password protection no dashboard.

**Próximo passo:**
- **W3-C11 — Máquina de Estados (14 estados, 4 rotas):** `TRANSITION_RULES` em `domain/state_machine/rules.py` (cobertura ≥ 95%); pluga no botão "Confirmar movimentação" da tela de confirmação do C10 e popula `finalizada_em`/`ciclo_atual`.

**Definition of Done:** ✅ **atendida** (testes ≥80% domínio/serviço — 486/94,55%, domínio de provas 100%; anti-enumeração e idempotência QR/manual cobertas; sem erro de console/log crítico; error boundary `(app)` cobre a rota + degradação graciosa da câmera; animações com `prefers-reduced-motion`; RLS versionada e **aplicada no Supabase real** — `alembic_version=0014`, advisors sem achados novos; sem segredos versionados).

---

## Sessão 12 — 2026-06-15 — [Wave 2 / Componente C09] Tela de Configurações do Sistema (FECHA A WAVE 2)

**Objetivo:** Configurações do sistema (RF-022), exclusivas do 3Studio: tempo de atraso (RN-008/US-016) e template de etiqueta (RN-011), persistidos em `system_settings` com RLS, consumíveis server-side (etiqueta C06 agora; dashboard C16 depois). Último componente da Wave 2.

**Decisões (respostas dos Pontos de Decisão §4 — tudo conforme recomendado):**
- **DP-1** modelo **chave-valor** (`system_settings`) + registro de domínio (defaults/validação por chave). **DP-2** RLS **leitura `authenticated`** / **escrita admin-only** (valores não-sigilosos alimentam C16/C06 na própria sessão RLS — sem SECURITY DEFINER). **DP-3** página **3Studio-only** pelo flag `administrador` (proxy C05 + gate `Recurso.CONFIGURACOES` + RLS). **DP-4** **sem cache** — leitura fresca = imediato (US-016). **DP-5** "personalizado" = sobrescrita dos **5 campos do `EtiquetaTemplate`** do C06 (o gerador só passa a **ler** a config). **DP-6** settings desta sessão = **tempo de atraso + template**, **save por card**.

**Feito:**
- **Recon (workflow de 7 agentes)** confirmou o estado real e divergências do prompt: o recurso/rota/nav **`configuracoes` já existiam** (C05, admin-only); **não há cache** no `apps/api`; o `EtiquetaTemplate` do C06 expõe **só 5 campos**; prefixo HTTP real é **sem `/api`**; próxima migration **0013**; próximo ADR **047**.
- **Backend:** migration **`0013`** (`system_settings` chave-valor + RLS: SELECT authenticated, INSERT/UPDATE admin, sem DELETE) + espelhos `migrations/rls/system_settings_*.sql`. Domínio `domain/settings.py` (registro de chaves: defaults/validação + `ConfiguracaoEtiqueta` + `efetivar_*`); `SettingsRepositoryPort`/`SqlAlchemySettingsRepository` (upsert idempotente, sem commit); `SettingsService` (`listar`/`salvar`/`obter_config_etiqueta`); router `/settings` (`GET`+`PUT/{chave}`) gateado por `get_settings_service`. **Integração C06:** `EtiquetaPort.gerar_pdf(... , config)`; `_template_efetivo`; `ProvasConsultaService.gerar_etiqueta` lê a config na mesma sessão RLS.
- **Frontend:** `/configuracoes` (server fino → `ConfiguracoesView` client): cards **Tempo de atraso** e **Template de etiqueta** com **Salvar por card**, validação em tempo real, estados carregando/erro(retry)/**restrito (403)**, toast; `lib/api/configuracoes.ts`. Segmented Modo com pílula `layoutId` + teclado WAI-ARIA; reveal por `AnimatePresence`; reduced-motion. `nav-items.ts` sem o marcador placeholder.
- **Revisão adversarial (workflow de 14 agentes, 4 dimensões × verificadores céticos):** **7 confirmados** (2 médios, 5 baixos), todos corrigidos — **`qr_zona_quieta_modulos`** ignorado (lia `self._t`, não o template efetivo) → fix + teste por bytes; segmented sem teclado → navegação WAI-ARIA; save-padrão gravava dimensões antigas → grava defaults; `toastRef` morto removido; +testes (save-padrão, teclado, reduced-motion, payload completo).
- **Deploy:** migration **`0013`** aplicada no **Supabase real** via MCP (tabela + RLS + 3 policies + bump `alembic_version=0013`); advisors de segurança sem achados novos.
- **Refino pós-entrega (a pedido do dono):** padding horizontal maior no segmented de **Modo** (`.segmentoItem`) — vale para "Padrão" e "Personalizado".
- **Docs:** `docs/configuracoes.md`; **ADR-047 a ADR-051**; CLAUDE.md §9.

**Testes / cobertura:**
- api: **461 verdes (offline + `@db`, PG 17 local 5433), cobertura 95%** — `test_settings_dominio.py`, `test_settings_service.py`, `test_equivalencia_rls_system_settings.py`, `test_etiqueta_pdf.py` (config + qr), `test_settings_endpoints.py` (@db: defaults, delay imediato, 422, **403 não-3Studio**, etiqueta padrão×personalizado), `test_rls_system_settings.py` (@db: escrita admin-only, leitura authenticated, sem DELETE), `test_migrations.py` (head `0013`). `ruff`/`ruff format`/`mypy --strict` limpos.
- web: **122 verdes** (`configuracoes-view.test.tsx`: render, salvar delay+toast, validação sem API, personalizado revela+salva objeto completo, save-padrão, teclado, reduced-motion, 403→restrito, erro→retry); E2E `e2e/configuracoes.spec.ts` (proteção + live opt-in). `pnpm lint`/`build` limpos.

**Pendências / em aberto:**
- [x] **Migration `0013` aplicada no Supabase real** (via MCP): `alembic_version=0013`, `system_settings` + RLS (3 policies); advisors sem achados novos (os 2 pré-existentes — RLS-no-policy do `alembic_version` lockado e leaked-password — permanecem).
- [ ] **Responsável (operação):** nada novo obrigatório p/ o C09 (a página funciona com os defaults; o admin salva quando quiser). Pendências antigas seguem (R2_*, política de senha, leaked-password protection).
- [ ] **Wave 2 concluída** — sugerir **auditoria da Wave 2** (C06→C09) antes da Wave 3, como na Wave 1.

**Próximo passo:**
- **W3-C10 · Escaneamento por Câmera + Fallback Manual (Mobile-First)** — abre a Wave 3 (fluxo de movimentação). Sugerido **auditar a Wave 2** antes.

**Definition of Done:** ✅ atendida (code review adversarial + remediação; testes ≥80% domínio/serviço; migration+RLS versionadas e aplicadas; acesso negado a não-3Studio em middleware **e** RLS; sem erros de console/log; docs do módulo; error boundary do grupo `(app)`; animações com reduced-motion; sem segredos versionados).

---

## Sessão 11 — 2026-06-15 — [Wave 2 / Componente C08] Visualização de Prova (Detalhe)

**Objetivo:** Página de detalhe da prova (`/provas/[id]`): arte, metadados completos, rota/status, ciclo atual, ações de etiqueta (visualizar/baixar) e o histórico em empty state — universal, com escopo pela RLS e redirect sem vazar existência.

**Feito:**
- **Recon (workflow de 5 agentes)** confirmou o estado de C04/C05/C06/C07 e revelou divergências do prompt: `useAuthorization` **não existe** (C05 = `access-matrix`+proxy+`RbacFlash`); a etiqueta do C06 era **admin-only** (colidia com o detalhe universal); não havia `GET /provas/{id}`; a `StoragePort` **não tem URL pré-assinada**; rótulos de rota viviam em `lib/api/provas.ts`.
- **Backend:** migration **`0012`** (`provas.ciclo_atual` NOT NULL default 1 — DP-1); `ProvasConsultaService` ganhou `obter`/`obter_arte`/`gerar_etiqueta` (+ deps opcionais `storage`/`etiqueta`); `ProvasService` perdeu a etiqueta (só criação). Endpoints `GET /provas/{id}` (detalhe), `GET /provas/{id}/arte` (**proxy** do R2 — DP-5) e etiqueta migrada para o serviço **universal RLS-escopado** (DP-8) — os três por `get_provas_consulta_service`; fora-do-escopo == inexistente == **mesmo 404** (anti-enumeração §11).
- **Frontend:** `/provas/[id]` (server fino `key={id}` + `ProvaDetalheView` client): busca `obterProva`; 404 → toast + `router.replace('/provas')`; arte por proxy (blob→objectURL→`<img>`); "Visualizar etiqueta" em `MotionModal`, "Baixar" via blob; "Voltar" = `router.back()`+fallback; histórico em empty state. Módulo **`lib/provas/rota-labels.ts`** (DP-7); `ProvaDetalhe`/`obterProva`/`baixarArte`; token `--app-card-white`.
- **Revisão adversarial (workflow de 14 agentes, 4 dimensões × verificadores céticos):** 10 achados, **5 confirmados (todos baixos)**, corrigidos: arte ausente no R2 de prova visível → **404** (não 503) + log de órfã; **vazamento do objectURL** da etiqueta no unmount com modal aberto → efeito de cleanup; 2 docstrings-fóssil (topo de `http/provas.py`; `(DP-7)`→`(RF-003)` em `provas.ts`).
- **Refino de animações (pós-entrega, a pedido do dono):** fade-in da arte ao carregar o blob; cascata do card de histórico após o de detalhe (`delay 0.07`); feedback tátil (`SPRING` `scale 0.97`) em Voltar/Visualizar/Baixar — tudo transform/opacity + reduced-motion. + ajustes manuais de layout do dono (bordas removidas do Voltar/card; fontes `nome`/`campoValor` levemente menores).
- **Etiqueta — molduras pontilhadas removidas (C06, a pedido do dono):** o PDF saía com 4 caixas tracejadas (`_caixa_pontilhada`) "como no design"; removidas as chamadas + o helper (`set_dash_pattern`). Mantidos os contornos sólidos e o texto; verificado por render. Emenda à ADR-038. `test_etiqueta_pdf.py` verde.

**Decisões (ADRs):**
- **ADR-046** (DP-1..DP-8): `ciclo_atual` (0012, incrementado pelo C15); histórico empty state (fronteira C11/C13); sem botões Cancelar/Reiniciar (C14/C15); preview de etiqueta em modal; **arte por proxy** (rejeitada a pré-assinada); 404 idêntico + Voltar=back+fallback; módulo de rótulos de rota; **etiqueta universal-em-escopo** (deixou de ser admin-only). Reconciliações de design na CLAUDE.md §2.1.

**Testes / cobertura:**
- api: **263 offline / 395 com `@db`** (`REQUIRE_DB_TESTS=1`, PG 17 local 5433) — novos `test_provas_detalhe.py` (serviço: detalhe/arte/etiqueta, 404 genérico, arte-antes-do-storage, arte ausente→404, fallback `-`) e `test_provas_detalhe_endpoints.py` (@db: **escopo por perfil**, **anti-vazamento** fora-do-escopo==inexistente com mensagem idêntica, `ciclo_atual`/`vendedor_nome`, proxy da arte, etiqueta universal); `test_provas_endpoints.py` (etiqueta acessível ao vendedor dono); `test_migrations.py` (head 0012). `ruff`/`ruff format`/`mypy --strict` limpos.
- web: **113 verdes** (`prova-detalhe-view.test.tsx`: render fiel, arte por proxy, 404→toast+redirect, baixar/visualizar etiqueta, Voltar, erro+retry, revogação do objectURL no unmount); E2E `e2e/prova-detalhe.spec.ts` (proteção + live opt-in). `pnpm lint`/`format:check`/`build` limpos.

**Pendências / em aberto:**
- [x] **Migration `0012` aplicada no Supabase real** (via MCP, **pós-entrega**, ao diagnosticar a listagem quebrada — ver abaixo): `alembic_version=0012`, coluna `ciclo_atual` NOT NULL default 1; advisors de segurança sem achados novos.
- [ ] Rodar `pnpm test:e2e` com `E2E_LIVE=1` quando houver stack + sessão (suite live opt-in). Demais pendências de operação do C06/C07 (vars `R2_*`, role de runtime, leaked-password) seguem em `DECISIONS.md`.

**Incidente pós-entrega (mesma sessão):** a tela `/provas` (listagem do C07) parou de carregar ("Não foi possível carregar as provas"). **Causa:** o C08 adicionou `ciclo_atual` ao modelo ORM **compartilhado** `ProvaRow`, então `select(ProvaRow)` (listagem E detalhe) passou a projetar `provas.ciclo_atual`; como a `0012` ainda **não** estava aplicada no Supabase real (estava em `0011`), a query batia em coluna inexistente → 500. **Mesmo padrão do C07** (a `0010` que faltava derrubou a listagem). **Fix:** aplicada a `0012` em produção (SQL de `alembic upgrade 0011:0012 --sql` + bump do `alembic_version`); listagem volta a carregar. **Lição:** migration que altera o modelo ORM compartilhado precisa ir a produção **junto** com o deploy do código (a `0012` deveria ter sido aplicada no encerramento, como C06/C07 fizeram com 0009/0011).

**Próximo passo:**
- **W2-C09 · Tela de Configurações do Sistema** (parametrização da etiqueta — RN-011 — e demais ajustes).

**Definition of Done:** ✅ atendida (testes ≥80% domínio/serviço; integração @db verde; migration versionada/up-down **e aplicada em produção**; escopo por perfil + anti-vazamento testados; arte sem URL pública; error boundary do grupo; animações com `prefers-reduced-motion`; sem segredos versionados; gates verdes).

---

## Sessão 10 — 2026-06-15 — [Wave 2 / Componente C07] Listagem, Pesquisa e Filtros de Provas

**Objetivo:** Entregar a tela de **operação diária** — listar/buscar/filtrar provas com paginação server-side, escopo por perfil (UI + RLS), tabela igual à do C04.

**Grounding (antes de codar):** investigação multi-agente do estado real (C04/C05/C06) que **corrigiu 3 premissas do prompt**: (1) **não existe** `useAuthorization(...).scope` — C05 só entregou RBAC de página (`can`/`podeAcessarRota`); (2) o prefixo real é **`/provas`**, não `/api/provas`; (3) **descoberto** que a coluna "Vendedor" quebraria sob a RLS de `usuarios` para 3Studio/Clicheria não-admin e Motorista.

**Decisões do dono (Pontos de Decisão, 1 rodada):** DP-1 = **Replicar** a tabela do C04 (não extrair `<DataTable>`); DP-5 = **scroll infinito + filtros na URL**; DP-4 = **rótulos curtos por estado (14)**; DP-7 (descoberto) = **função SECURITY DEFINER id→nome**. DP-2/DP-3/DP-6 = recomendações (adaptar barra por escopo; adicionar `finalizada_em`; `GET /provas` sem gate de admin, "Ver"→`/provas/[id]`). → ADR-041 a ADR-045.

**Feito:**
- **Backend:** migration **`0010_listagem_provas`** (`provas.finalizada_em timestamptz NULL` + índice parcial; função **`public.nomes_de_vendedores(uuid[])`** SECURITY DEFINER + espelho `migrations/rls/`). Porta `ProvasRepositoryPort` estendida (`FiltrosProvas`/`PaginaProvas`, `listar`/`vendedor_ids_distintos`/`nomes_de_vendedores`); `ProvasConsultaService`; dependência **`get_provas_consulta_service`** (universal, sessão RLS fail-closed); endpoints **`GET /provas`** (busca+filtros+paginação, ordem `created_at desc`, sem N+1) e **`GET /provas/vendedores`** (dropdown escopado).
- **Frontend:** `/provas` real (`ProvasView` replicando a tabela do C04 — C04 intocado), barra de filtros de 2 linhas, **estado na URL** (debounce 300ms, "Limpar"), **adaptação por perfil** (esconde Vendedor no escopo "as próprias"), "Ver"→`/provas/[id]` (placeholder **C08**); módulo `lib/provas/status-labels.ts` (14 rótulos); `escopoDeProvas`/`listarProvas`/`listarVendedoresProvas`. Animações por tokens; cards no mobile; loading/vazio/erro.

**Decisões (ADRs):** ADR-041 (replicar tabela + listagem universal), ADR-042 (filtros na URL + scroll infinito), ADR-043 (rótulos curtos/14), ADR-044 (`finalizada_em` aditiva, populada pelo C11), ADR-045 (nome do vendedor via SECURITY DEFINER, **endurecida na remediação** para re-aplicar o escopo do chamador) — todas **Aceitas**.

**Remediação da revisão adversarial (5 dimensões × verificadores céticos; 8/13 confirmados):** (alta) `ruff format` nos 3 arquivos novos — o gate de CI é `ruff format --check`, que eu não rodara; (média) `fetchUsuarioAtual` memoizado com React `cache()` (a página não re-busca o `/usuarios/me` do layout); (média a11y) `aria-label` redundante removido dos inputs envolvidos por `<label>` (WCAG 2.5.3); (baixa segurança) `nomes_de_vendedores` re-aplica o escopo do chamador no corpo (fecha o vetor de RPC direto do PostgREST); (baixas) data em UTC, `:focus-visible`, espaçador do "Limpar". Não corrigido por ser correto: literal de stagger `0.025` (cópia fiel do C04 — vai para o C19).

**Testes / cobertura:**
- **api 377 verdes** (`ruff format`/`ruff`/`mypy --strict` limpos): escopo por perfil @db incl. **3Studio não-admin e Motorista resolvendo o nome** (DP-7); **chamada RPC-style da função como Vendedor com id alheio → vazio** (hardening); filtros combináveis; busca nome/requerimento; períodos; paginação+ordenação; **contador de SELECTs provando ausência de N+1**; dropdown escopado; 401/403; `0010` up/down em `test_migrations`.
- **web 104 verdes** (lint 0 erros — 2 warnings pré-existentes em C04/C06; `build`/`format:check` ok): `provas-view.test.tsx` (render fiel, debounce, hidratação da URL, filtro→URL, adaptação por perfil, "Limpar", "Ver", vazio/erro/403). E2E `provas-listagem.spec.ts` (proteção offline + live opt-in).

**Pendências / em aberto:**
- [x] **Operação (feito nesta sessão):** migrations `0010`→`0011` aplicadas no Supabase real (`alembic_version=0011`, sem drift). O dono reportou a listagem em 500 → diagnóstico via MCP (prod estava em `0009`, sem `finalizada_em`/função); `0010` desbloqueou; os **advisors** flagraram a função SECURITY DEFINER em `public` como chamável por RPC (DEFAULT PRIVILEGES do Supabase) → **`0011`** move `nomes_de_vendedores` para o schema **`private`** (não exposto), revoga `anon`, concede só a `authenticated`. **Advisors limpos**, listagem funcional (admin vê as 2 provas; nome resolve via `private.nomes_de_vendedores`).
- [ ] O filtro **"Finalizada em"** só retorna resultados após o **C11** popular `finalizada_em` (por design).
- [ ] **C08** consome a rota `/provas/[id]` (hoje placeholder) e pode reusar `ProvaListagem`/rótulos/`status-labels`.
- [ ] (Opcional) Se o C08+ precisar do `usuario` no cliente, considerar um contexto no app shell para evitar o 2º `GET /usuarios/me` da página de provas.

**Próximo passo:**
- **W2-C08 · Visualização de Prova (Detalhe)** — comando: cole `PROMPTS/W2-C08-...md` no Claude Code com os arquivos de contexto + a imagem do design da tela de detalhe.

**Definition of Done:** ✅ atendida — testes (escopo por perfil, sem N+1, migration `0010` versionada/up-down, render/estados, `prefers-reduced-motion`), error boundary do grupo `(app)`, docs (`docs/provas-listagem.md`), sem segredos versionados, R$ 0.

---

## Sessão 09 — 2026-06-12 — [Wave 2 / Componente C06] Cadastro de Prova + Rota + Etiqueta

**Objetivo:** Abrir a Wave 2 com a porta de entrada do domínio: criação de provas com seleção manual de rota (imutável), código `PRV-AAAA-MM-NNNNNN`, QR, etiqueta PDF 95×55 e a RLS de `provas` que fecha a pendência do C05.

**Decisões do dono (Pontos de Decisão, 1 rodada):** DP-1 = **(A)** reconciliar a etiqueta (código em fonte grande abaixo do QR + rota como 5ª linha do bloco); DP-2 = 95×55 landscape confirmado, logos 3STUDIO + Studio&ART **fixas** (SVGs fornecidos em `apps/web/public/`); DP-3/4/5/6/7 = recomendações aceitas (código canônico + QR puro; enum completo 14 estados; sem PATCH + trigger; RLS com admin vendo todas; segno+fpdf2 sob demanda + toast/download/navegação). Rápidas: requerimento texto-de-dígitos; cliente texto livre; ano da etiqueta dinâmico.

**Feito:**
- Migrations **`0007_provas`** (enums, tabela, índices RNF-019, trigger de imutabilidade, RLS restritiva provisória) e **`0008_rls_provas_e_runtime_role`** (grants mínimos SELECT/INSERT, 6 policies por perfil, role `rastreio_runtime` NOBYPASSRLS) + espelhos 1:1 em `migrations/rls/` — ciclo `upgrade→downgrade→upgrade` limpo no PG 5433.
- Backend hexagonal: `domain/provas.py` (código/charset/regex p/ C10, magic bytes, vendedor ativo), portas `ProvasRepositoryPort`/`EtiquetaPort`, `ProvasService` (criação atômica: upload R2 → INSERT com retry de colisão → commit; compensação logada), adapter `FpdfEtiquetaGenerator` (vetorial, determinístico, template parametrizável), repositório SQLAlchemy, endpoints `POST /provas` + `GET /provas/{id}/etiqueta.pdf` (admin-only, 1 sessão RLS/request), `StorageError`→503.
- Frontend: `/provas/nova` real (cartão branco, segmented control de rota sem pré-seleção, dropzone, vendedores em 1 consulta, pós-criação com download automático + retry); `apiFetch` multipart + `apiFetchBlob`; `lib/api/provas.ts`.
- Dívidas herdadas absorvidas: **role não-owner** (ADR-034 item 3) e **`SqlAlchemyUnitOfWork` → `adapters/outbound/db/`** (W0-A-018).
- Etiqueta validada VISUALMENTE (PDF de amostra renderizado e comparado ao design — código e rota presentes, logos vetoriais ok).

**Decisões (ADRs):** **ADR-035** (modelo/trigger), **ADR-036** (código+QR puro), **ADR-037** (enum completo, fronteira C06↔C11), **ADR-038** (etiqueta segno+fpdf2/DP-1), **ADR-039** (RLS de provas + admin vê todas + role de runtime — fecha ADR-033/034), **ADR-040** (remediação da revisão adversarial).

**Revisão adversarial (multi-agente, pós-merge):** 4 dimensões × verificadores céticos → 15 achados confirmados (1 alto, 3 médios, 11 baixos), corrigidos na mesma sessão (migration **`0009`** + middleware + idempotência + a11y; ver ADR-040):
- **Alto:** etiqueta PDF dava **500 permanente** para travessão/aspas curvas/emoji (nome/cliente são texto livre) — corrigido com `core_fonts_encoding='windows-1252'` + sanitização cp1252; fallback de vendedor `—`→`-`.
- **Médios:** (a) **idempotência real** via `prova_id` (reenvio após timeout converge / 409 divergente); (b) **`BodyLimitMiddleware`** 12 MB pré-auth (anti-DoS); (c) **WITH CHECK de INSERT endurecido** (`0009`: status/código/vendedor) contra acesso direto via Data API.
- **Baixos:** R2 recalibrado p/ upload (read 60s, retries 3); roving tabindex + setas no radiogroup; aria nos erros de Vendedor/Rota; `Dropdown` `disabled`/`invalido`; `transition: color` removido; aviso de truncamento >100 vendedores; drifts de doc (`/api`, nanoid→secrets).

**Testes / cobertura (pós-remediação):**
- api: **349 verdes** (era 255 no início da wave; `REQUIRE_DB_TESTS=1`, PG 17 local 5433), cobertura **94.84%** (domínio e serviço de provas: **100%**); `ruff`/`ruff format --check`/`mypy --strict` limpos; ciclo Alembic limpo (head **0009**).
- RLS de provas validada célula a célula @db (vendedor só as suas; motorista só os 3 "Em Trânsito" via fixtures de status; studio/clicheria/admin todas; fantasma → **0**; INSERT só admin com invariantes; UPDATE sem grant; trigger rejeita rota até para owner) + **equivalência anti-drift** domínio↔sql↔migration.
- web: **94 verdes** (era 85; 17 arquivos); `eslint`/`prettier --check`/`next build` limpos; Playwright **9 verdes** (+ specs live gateados).

**Refinos pós-merge + deploy de infra (mesma sessão):**
- **UI (feedback do dono ao vivo):** tela `/provas/nova` sem scroll no desktop (cartão preenche o shell; folga inferior = lateral) + tipografia reduzida; folga da pílula no segmented de Rota; **etiqueta** com contornos afinados (~2px) e "Aponte a câmera para o QR CODE" centralizado sobre o QR. Commits `a21ac41`, `edc0cd4`, `09d6891`.
- **Infra via MCP:** migrations `0007`→`0008`→`0009` aplicadas no **Supabase real** (`rastreio-provas-digitais`/`wmpxxrzbzqgsorjwczvz`) — `alembic_version=0009`, sem drift (SQL de `alembic upgrade --sql` com os `UPDATE alembic_version`); estado verificado (provas/enums/trigger/6 policies/role runtime) + advisors de segurança sem achado sobre `provas`. Bucket **R2 `rastreio-provas-artes`** já existia (nada a criar).

**Pendências / em aberto:**
- [x] **Infra aplicada (sessão 09):** Supabase em `0009`; bucket R2 confirmado.
- [ ] **Dono (só segredos/dashboard):** 4 vars `R2_*` no ambiente da api (`R2_BUCKET=rastreio-provas-artes` + endpoint/keys via API token do Cloudflare); **(opcional)** ativar o role de runtime (`ALTER ROLE rastreio_runtime LOGIN PASSWORD ...` + `DATABASE_URL`); habilitar leaked-password protection (Auth — W1-A-011).
- [ ] Itens herdados que permanecem: `KEEPALIVE_DATABASE_URL` (W0-A-001), TTL do access token (DP-3 do C03), W1-A-006 (outbox), sink real de erros (C19/C20).
- [ ] C07 estende `ProvasRepositoryPort` com listagem paginada/filtros; C08 serve a arte (decidir bytes-via-backend vs presigned URL — a porta de storage não tem presigned hoje).

**Próximo passo:**
- **W2-C07 — Listagem, Pesquisa e Filtros de Provas** (a página `/provas` hoje é placeholder e recebe a navegação pós-criação).

**Definition of Done:** ✅ atendida (testes ≥80%/máquina de estados n/a nesta wave; migrations versionadas/documentadas; critérios US-001 e Matriz §7 validados com teste de acesso não autorizado por perfil; RLS versionada; sem N+1; idempotência/atomicidade verificadas; error boundary do grupo cobre a rota; animações com reduced-motion; sem segredos versionados; protocolo §10 executado).

---

## Sessão 08 — 2026-06-12 — [Wave 1 / Remediação] Auditoria da Wave 1 → GO

**Objetivo:** Resolver os achados de `docs/audits/AUDITORIA-WAVE-1.md` (escopo `PROMPTS/W1-REMEDIACAO-wave1.md`) — Críticos/Altos primeiro — re-verificar a Wave 1 inteira e atualizar o veredito para **GO** antes da Wave 2.

**Decisões do dono (1 rodada):** W1-A-001 = endurecer in-repo agora (fail-closed) + adiar o role não-owner ao C06; W1-A-006 = aceitar como dívida rastreada; escopo = remediação in-repo completa (+ seam de captura); ações de dashboard (leaked-password + política de senha; aplicar migrations) com o dono — **hook já habilitado** por ele.

**Feito (19 achados Resolvidos · 0 falso-positivo · grounding multi-agente antes de cada fix):**
- **W1-A-001 (Alto):** `abrir_sessao_rls` + `create_request_session_factory` (`_RlsSyncSession` + guarda `after_begin`) → sessão de request **fail-closed** (sem claims → levanta, não lê como owner). Sistema/seed seguem owner de propósito. Role não-owner → C06. (ADR-034)
- **W1-A-002 (Alto):** `middleware.test.ts` cobre o enforcement do proxy (não-admin→redirect+flash; admin→next; não-auth→sem getClaims).
- **W1-A-003/005 (Méd):** 4 redirects → `HOME_PADRAO` (`/dashboard`); teste pós-login reescrito; E2E alinhado.
- **W1-A-004 (Méd):** `SET search_path = ''` nas 5 funções (hook+helpers) + migration **`0006`** p/ o banco real; `test_migrations` head=0006.
- **W1-A-007/008/009 (Méd):** `ruff format`/`prettier` reaplicados (gates verdes); **correção da narrativa:** o SESSION_LOG do C04/C05 dizia "format verde", mas o gate estava vermelho no HEAD auditado — reaplicado nesta sessão e agora **realmente verde** (api `ruff format --check` 77 ok; web `prettier --check` ok).
- **W1-A-010/013/014/015/016/017/018/019/020/021/036:** issuer do JWT (config-gated); órfão `created_at` ausente converge; `(app)/error.tsx` + seam `reportClientError`; testes do bootstrap (0%→100%) e dos helpers de RLS; drifts de doc (README RLS, 0002, auth/usuarios/app-shell).

**Decisões (ADRs):** **ADR-034** (sessão de request fail-closed; role não-owner adiado ao C06; + issuer/search_path; W1-A-006 = dívida).

**Testes / cobertura (re-verificação §4, saída real):**
- api: **255 verdes** (era 229), cobertura **95.12%** (piso 80); `ruff`/`ruff format --check`/`mypy --strict` limpos; ciclo Alembic upgrade→downgrade→upgrade limpo (head 0006).
- web: **85 verdes** (era 76, 16 arquivos); `eslint`/`prettier --check`/`next build` limpos.
- RLS positivo+negativo (fail-closed) + helpers default-deny; equivalência da Matriz intacta.

**Pendências / em aberto:**
- [ ] **Dono (dashboard):** habilitar **leaked-password protection** + **política de senha** (min 8, letras+dígitos) — W1-A-011/DP-3; e rodar `alembic upgrade head` no Supabase real (aplica `0006`).
- [ ] **Dívida rastreada:** W1-A-006 (reordenar recheck RN-010 / outbox); **role não-owner `NOBYPASSRLS`** da RLS → **C06** (junto dos GRANTs de `provas`); W1-A-017 sink real de erros → C19/C20.
- [ ] Itens herdados: `KEEPALIVE_DATABASE_URL` (W0-A-001), TTL do access token (DP-3 do C03), mover `SqlAlchemyUnitOfWork` p/ `adapters/outbound/db/` no C06 (W0-A-018).

**Próximo passo:**
- **W2-C06 · Cadastro de Prova com Seleção de Rota + Etiqueta** — abre a Wave 2 e aplica a RLS de `provas` sobre a fundação fail-closed deste sessão. *(O prompt de remediação citou "W2-C07", mas o roadmap do Backlog/CLAUDE.md §7 e o SESSION_LOG têm o **C06** como primeiro da Wave 2 — divergência registrada, CLAUDE.md §2.1.)*

**Definition of Done:** ✅ Veredito **GO** — re-verificação inteira verde; cada achado Resolvido tem teste/commit; dívida remanescente rastreada e não-bloqueante; protocolo de encerramento executado.

---

## Sessão 07 — 2026-06-12 — [Wave 1 / W1-C05] Controle de Acesso por Perfil (Matriz RBAC em duas camadas)

**Objetivo:** Formalizar o RBAC por perfil em **duas camadas independentes** (proxy do App Router + RLS do PostgreSQL), com a Matriz §7 como fonte única, fechando a **Wave 1**.

**Feito:**
- **Hook de claims** (migration `0004`): `public.custom_access_token_hook` eleva `setor`/`user_id`/`administrador` do `app_metadata` ao topo do JWT (posição lida pela RLS), `SECURITY INVOKER`, grants restritos ao `supabase_auth_admin`.
- **RLS definitiva de `usuarios`** (migration `0005` + espelhos em `migrations/rls/`): grants a `authenticated` + policies `self`/`admin` (opção 6-A), **helpers** `app_current_claims/app_setor/app_is_admin/app_current_user_id` (reuso no C06), `_roles.sql` (stand-ins locais). Removido `usuarios_baseline_restritiva.sql`.
- **Propagação de claims (ADR-008)**: `propagar_claims_rls` (listener `after_begin` + `SET LOCAL ROLE authenticated`) ligado em `get_usuarios_service`; guard generalizado em `requer_acesso(Recurso)` + `domain/rbac.py`.
- **Camada superior (web)**: `lib/access-matrix.ts` (+ `access-matrix.cells.json`), enforcement no `proxy.ts` (claims via `getClaims()`, redirect + flash), `RbacFlash` (toast), **sidebar filtrada** por perfil.
- **Harness de equivalência** travando `access-matrix.ts` (web) e `rbac.py` (api) à Matriz canônica; **`docs/rbac.md`**.

**Decisões (ADRs):**
- ADR-029 (hook lê `app_metadata` do evento — opção B), ADR-030 (duas camadas + equivalência/PR único), ADR-031 (propagação `after_begin` + helpers portáteis — finaliza **ADR-008**), ADR-032 (RLS de `usuarios` 6-A), ADR-033 (fronteira C05↔C06). **DP-1…DP-7 confirmados** pelo dono ("segue com as recomendações"): Matriz ortogonal (Vendedor-Admin vê páginas admin), hook opção B, redirect→`/dashboard`+cookie, RLS 6-A.

**Testes / cobertura:**
- api: **229 verdes, cobertura 90%** (hook por perfil + evento malformado; RLS de `usuarios` sob `SET ROLE authenticated`; propagação ADR-008 + controle negativo; equivalência da Matriz; ciclo upgrade/downgrade das `0004/0005`). `ruff`/`mypy` limpos. **Revisão adversarial de segurança** (5 lentes): 2 achados de baixo risco endurecidos no hook (SECURITY INVOKER explícito + guard de evento malformado).
- web: **76 verdes** (access-matrix por célula, equivalência, sidebar por perfil, `RbacFlash`); `lint`/`build` limpos.
- Cobertura de células: **100% das de PÁGINA** (proxy/`can` ⇔ `autorizar`); **dado de `usuarios`** via RLS (admin todas; não-admin 0 alheias). 

**Pendências / em aberto:**
- [ ] **RLS de linha de `provas` (Vendedor as próprias / Motorista as "Em Trânsito") é do C06** (DP-3) — usando os helpers desta sessão; o harness é estendido lá.
- [ ] **Habilitar o hook no dashboard** do Supabase (Auth → Hooks → `public.custom_access_token_hook`) — passo de projeto (não-código). Aplicar `0004/0005` no projeto real via `alembic upgrade head`.

**Próximo passo:**
- **W2-C06 · Cadastro de Prova com Seleção de Rota + Etiqueta** (abre a Wave 2; aplica a RLS de `provas` sobre os helpers do C05).

**Definition of Done:** ✅ atendida (testes ≥ piso incl. acesso não autorizado por perfil + equivalência; RLS versionada em `/migrations/rls/`; migrations `upgrade`/`downgrade` em ambiente limpo; sem erro de console/log crítico; docs do módulo; sem segredos versionados; idempotência preservada). Itens de animação reusam o sistema do C04.

---

## Sessão 06 — 2026-06-12 — [Wave 1 / W1-C04] Cadastro e Gestão de Usuários + App Shell

**Objetivo:** CRUD de usuários (RF-018, RF-020, US-015) com provisionamento via Supabase Auth Admin API, **primeira tabela/migration de domínio** (`usuarios`) e o **app shell** (sidebar + área de conteúdo) que hospeda toda a plataforma autenticada.

**Feito:**
- **Pré-flight** — limpeza de `__pycache__` órfãos (resíduo de tentativa anterior de C04) e commit do ajuste cosmético pendente do C03 (`login.module.css`).
- **Tokens do design** — o MCP do Figma estourou o limite do plano Starter; extração feita por **amostragem de pixel dos exports PNG 1:1** (Downloads: `Gerenciamento de usuários - admin (3).png` + `- Modal (1).png`; lossless → cores exatas) com 3 sondas Python/Pillow: paleta completa (`#eaeaea` shell r40, `#ff5959` Desativar, `#d7d7d7` controles, `#979797` divisores, scrim `rgba(0,0,0,.76)` medido, modal idêntico aos tokens `--auth-*` do C03), geometria (colunas da tabela com frações medidas, pills 56/29px, pitch 56px) e tipografia. Tokens centralizados em `globals.css` (`--app-*`).
- **Backend** — migration **`0002_usuarios`** (enums `setor_enum`/`localizacao_enum`, PK = UUID de `auth.users` 1:1, CHECK bidirecional RN-009, índices RNF-019, **RLS restritiva** aplicada e versionada em `migrations/rls/usuarios_baseline_restritiva.sql`; ciclo upgrade→downgrade→upgrade validado em PG 16 real porta 5433); domínio puro (`domain/usuarios.py`); portas `IdentityProviderPort`/`UsuariosRepositoryPort`; **`UsuariosService`** com provisionamento coordenado (**compensação** em falha parcial, **adoção de órfãos marcados** via `app_metadata.provisionado_por`, **fail-closed** nas mutações de status, salvaguarda do **último admin ativo**, sync de `app_metadata.{setor,administrador}` p/ o C05); adapter **`SupabaseAdminIdentityProvider`** (httpx, `sb_secret` server-only) + stand-in 503; endpoints `/usuarios` (listagem paginada server-side com busca escapada + filtros, criar, editar com e-mail imutável, desativar/reativar idempotentes, `/me`) com **guard mínimo de admin**; task **`bootstrap_admin`**; `.env.example` com `SUPABASE_SECRET_KEY`.
- **Frontend** — **app shell** no grupo `(app)` (`AppShell` + `Sidebar` com indicador ativo via `layoutId`, busca inerte, rodapé via `GET /usuarios/me` com fallback gracioso; placeholders DP-6; transição de conteúdo por rota); **Gerenciador de usuários** fiel ao design (debounce 300ms, filtros server-side, scroll infinito na área da tabela, mutações em memória); **`MotionModal`** reutilizável (DAT §5.2, focus trap, reduced-motion) + form Novo/Editar (validação em tempo real, localização condicional p/ Vendedor, 409 inline) + confirmação de status; **toasts** (`useToast`); **responsivo** DP-7 (drawer/cards/folha, ≥44px). Rotas `/`, `/login`, `/inicio` → `/usuarios`; `AuthProof`/`ApiStatus` removidos (mortos).
- **Fidelidade visual** — verificada por rota de preview temporária + screenshot Playwright **1920×1080 comparado pixel a pixel** com os exports (cores idênticas; scrim `#343434` vs `#333333`); preview removido antes do commit.
- **Qualidade** — api: ruff + mypy strict verdes, **201 testes** (90% cobertura) incl. compensação com PG real e estrutura da migration; web: eslint + prettier + build verdes, **50 testes** vitest + Playwright 8/8 (5 live gated); **revisão adversarial multi-agente** (5 dimensões × céticos) sobre os dois commits.
- **Docs** — `docs/usuarios.md`, `docs/app-shell.md`; CLAUDE.md §2.1/§5.5-5.6/§6/§9; README (deploy confirmado, setup C04, roadmap); CHANGELOG (duas seções `### Fixed` consolidadas).

**Decisões (ADRs):**
- **ADR-023** — DP-1: modelo **Setor × Administrador ortogonal** (o design governa) + releitura da Matriz §7 p/ o C05; refletida em CLAUDE.md §2.1.
- **ADR-024** — DP-2: `usuarios` 1:1 com `auth.users` (PK = UUID do auth, sem FK física) + schema/índices.
- **ADR-025** — DP-3/DP-4: provisionamento via Admin API (httpx, sem SDK), compensação/adoção de órfãos, `SUPABASE_SECRET_KEY` server-only, desativar = ban + `ativo=false` (US-015), e-mail imutável.
- **ADR-026** — app shell como layout do grupo `(app)` (DP-6/DP-7/DP-9: lucide-react, wordmark do C03, status no 2º dropdown, scroll infinito, "Satus"→"Status").
- **ADR-027** — DP-5: guard mínimo de admin agora + RLS provisória + `app_metadata`; RBAC completo no C05.
- **ADR-028** — DP-8: `MotionModal`/toasts criados já no contrato do C19 (que generaliza sem reescrever).

**Testes / cobertura:**
- api: `uv run pytest` → **201 passed** (REQUIRE_DB_TESTS=1, PG 16 real), cobertura **90%** (fail_under 80); ruff + mypy strict limpos.
- web: `pnpm test` → **50 passed** (10 arquivos); `pnpm test:e2e` → 8 passed + 5 live-gated; lint/build/format verdes.

**Pendências / em aberto:**
- [ ] **Responsável:** cadastrar `SUPABASE_SECRET_KEY` no backend (Railway/.env), configurar a **política de senha** no dashboard (min. 8, letras+dígitos), rodar `alembic upgrade head` no Supabase real e o `bootstrap_admin` do primeiro administrador.
- [ ] Visibilidade dos itens de menu por perfil + enforcement de rota + RLS por perfil + Custom Access Token Hook → **C05**.
- [ ] Busca global da sidebar (inerte até a Wave 2); reset/troca de senha (componente futuro); "página inicial do perfil" (C05).
- [ ] Itens herdados: W0-A-001 (`KEEPALIVE_DATABASE_URL`), TTL do access token (DP-3 do C03), W0-A-018 (mover `SqlAlchemyUnitOfWork` p/ `adapters/outbound/db/` no C06).

**Próximo passo:**
- **W1-C05 · Controle de Acesso por Perfil — Matriz RBAC** (access-matrix.ts + enforcement no proxy + políticas RLS por perfil + Custom Access Token Hook, sobre o `app_metadata` já gravado).

**Definition of Done:** ✅ atendida — testes (incl. provisionamento/RN-009/RN-010/idempotência), migration versionada e documentada, RLS versionada em `migrations/rls/`, sem erros de console/log crítico, docs do módulo, animações validadas com `prefers-reduced-motion`, sem segredos versionados, árvore limpa.

**Pós-entrega (mesma sessão):**
- **Suporte live ao dono:** o 500 em `/usuarios` no ambiente real era a migration `0002` não aplicada no Supabase — `alembic upgrade head` executado lá + primeiro admin provisionado por upsert direto (a `SUPABASE_SECRET_KEY` ainda não está no `.env`; sem ela, criar/editar/desativar respondem 503 — pendência do responsável).
- **Revisão adversarial concluída** (38 agentes; 27 confirmados/6 refutados) → correções em dois commits `fix(w1-c04)`: concorrência no backend (adoção de órfão com idade mínima, lock otimista + 409, RN-010 com advisory lock transacional, idle-in-transaction, bootstrap reordenado, migration **`0003`** trancando `alembic_version` no PostgREST — aplicada no Supabase real, `/docs` off em produção, JWKS timeout) e robustez no frontend (loop infinito do scroll, corrida de paginação, timeout combinado, modais durante submit, drawer back/forward, signOut, motion/ARIA/touch). api: **207 testes**, 90%; web: **50 testes**.
- **Fidelidade (feedback do dono):** sidebar/conteúdo escalados ao quadro de 1080px do Figma via unidade `--u` — pixel a pixel em 1080 (±2px), proporcional em janelas menores.
- Refutados pela verificação cética (sem ação): cap da busca por e-mail, acesso do desativado até o TTL (mitigado pelo ban+revogação), `layoutId` duplicado desktop/drawer, falta de `error.tsx` no grupo, ILIKE sem índice dedicado (escala ~30 usuários).

---

## Sessão 05 — 2026-06-11 — [Wave 1 / W1-C03] Tela de Login e Sessão

**Objetivo:** Autenticação por e-mail/senha (Supabase Auth), sessão stateless em cookie + refresh, encerramento por inatividade de 30 min, verificação de JWT no backend e as **três telas do design** — primeiro componente da Wave 1.

**Feito:**
- **Backend** — `JwtVerifier` (`adapters/inbound/http/auth.py`): **ES256 via JWKS** cacheado (`PyJWKClient`) + **HS256 fallback**, valida `aud="authenticated"`/`exp`, rejeita `alg=none` e confusão de algoritmo; **`GET /auth/me`** (prova). `Settings` ganhou `SUPABASE_JWKS_URL`/`effective_jwks_url`; dependência `pyjwt[crypto]`. 18 testes offline; ruff + mypy + pytest verdes (cobertura **98%**, 104 passed/7 skipped).
- **Frontend** — clients **`@supabase/ssr`** (browser/servidor) + `updateSession` + **`src/proxy.ts`** (só refresh; `getUser()`); **três telas** em CSS Modules fiéis ao Figma (`/login` adaptativa desktop-split/mobile, `/bem-vindo`, `/inicio` placeholder com `AuthProof → /auth/me` + Sair); **erro de login genérico**; **inatividade 30 min** (`InactivityGuard`); fundação de **motion** (tokens DAT §5.1 + `useReducedMotion`) com **Framer Motion** (transform/opacity, reduced-motion-aware). **Inter** self-hospedada; herói **17,8 MB → 540 KB**. **vitest 11/11** + **Playwright 4/4** (+1 *live* gated); `pnpm lint`/`build` verdes; fidelidade conferida por screenshots.
- **Docs** — `docs/auth.md`; `.env.example` (api/web) atualizados.
- **Refino (pós-feedback do dono):** (1) fluxo mobile corrigido — **boas-vindas primeiro**, login revelado ao clicar em "Entrar", em **rota única `/login`** (`<AuthFlow>`, troca de passo, sem redirect por viewport); `/` e `/bem-vindo` redirecionam para `/login`; `export const viewport` adicionado. (2) Herói do desktop com o **formato custom EXATO do Figma** (máscara SVG). (3) Animações (fade do contorno no foco dos campos, hover/press dos botões, transição boas-vindas→form; **imagem-herói estática** — parallax/zoom removidos a pedido do dono). (4) **Harmonização do motion:** contorno do input com **fade-in/out** no foco (overlay de opacity) e **mola única `SPRING`** (`tokens.ts`) para todas as interações + stagger/easing consistentes (emenda ADR-020). `Welcome`/`bem-vindo.module.css` removidos. vitest 11/11 + Playwright 5/5 verdes; screenshots reconferidos. **ADR-022.**

**Decisões (ADRs):**
- **ADR-018** (auth/sessão), **ADR-019** (verificação JWT ES256/JWKS+HS256 — corrige a premissa HS256), **ADR-020** (fundação de motion C03↔C19), **ADR-021** (`proxy.ts` no Next 16), **ADR-022** (fluxo adaptativo em rota única + herói custom + animações, refino); **emendas** ADR-014 (Inter local) e ADR-009 (Vercel + Railway confirmados).
- **Pontos de decisão (respostas do dono):** DP-1 ✓ · DP-2 = ES256/JWKS+HS256 + publishable moderna · DP-3 ✓ · DP-4 = `/inicio` · DP-5 = link inerte · DP-6 = instalar Framer Motion · DP-7 ✓ (breakpoint 768px) · DP-8 = tokens via link do Figma.

**Testes / cobertura:**
- Backend: **104 passed / 7 skipped (@db)**, cobertura **98%**. Web: **vitest 11/11**, **Playwright 4/4** (+1 *live* gated). ruff/mypy/eslint/`next build` verdes.

**Pendências / em aberto:**
- [ ] **Reset de senha** (fora do escopo do C03 — DP-5; link inerte por ora).
- [ ] **Caminho feliz E2E autenticado**: atrás de `E2E_LIVE` (requer usuário semeado + API rodando; a checagem `getUser` do servidor não é route-mockável). Sucesso já coberto pelo teste de componente.
- [ ] **Responsável:** ajustar o **TTL do access token** no dashboard (DP-3); cadastrar `KEEPALIVE_DATABASE_URL` (W0-A-001, herdada).
- [ ] Node Figma `70:171` (login mobile) reproduzido por tokens compartilhados + PNG anexado (rate limit do Figma Starter) — revalidar se necessário.

**Próximo passo:**
- **W1-C04 · Cadastro e Gestão de Usuários.**

**Definition of Done:** ✅ (subconjunto aplicável ao C03): testes verdes; sem erro de console/log crítico; docs do módulo (`docs/auth.md`); error handling (401 genérico, error boundaries herdados); animações validadas com `prefers-reduced-motion`; sem segredos versionados. RLS/migrations **não se aplicam** ao C03 (tabelas de auth são do Supabase).

---

## Sessão 04 — 2026-06-11 — [Wave 0 / W0-REMEDIATION] Remediação da Wave 0

**Objetivo:** Corrigir os achados da auditoria (`docs/audits/wave-0-audit.md`) por severidade/dependência, com teste por correção e **gate de re-verificação**, sem regressão nem escopo novo (escopo de `PROMPTS/W0-REMEDIATION-remediacao.md`).

**Feito:**
- **29/29 achados endereçados** (0 Blocker · 0 High · 2 Medium · 16 Low · 11 Nit): **26 Resolvidos**, **1 Resolvido documental** (W0-A-018 → ADR-017, código na Wave 2), **1 Ação do responsável** (W0-A-001), **1 Parcial + dívida** (W0-A-029).
- **Medium:** W0-A-002 — CI dispara em push para `develop` (decisão do responsável); W0-A-001 — o responsável **cadastrará o secret** `KEEPALIVE_DATABASE_URL` (workflow mantido fail-loud, correto após o secret existir).
- **Robustez/observabilidade:** log da causa no readiness/`ping`/storage (003), R2 com timeouts (004), keep-alive sem vazar credencial na carga de config (005), `LOG_LEVEL` validado no boot (013), hermeticidade total da suíte vs. env de shell (012), downgrade defensivo da baseline (014).
- **Segurança HTTP:** guarda CORS curinga (015), security headers nosniff/no-store (016), whitelist de `X-Request-ID` (023), SHA-pinning de actions + Dependabot (008).
- **Frontend:** validação de shape + `error.tsx` (017). **Workflows:** permissions/concurrency/format:check/--no-dev (009/010/011/024). **Docs/ADRs:** emenda ADR-013 (007), ADR-017 (018), keep-alive §6 (006), `.env.example` (020/021), CLAUDE §5.1 (019), README (028); nits (022/025/026/027/029).
- Suíte **70 → 88 testes**, cobertura **100%** mantida. Log completo em `docs/audits/wave-0-remediation.md`.

**Decisões (ADRs):**
- **ADR-017** (novo): lar das implementações de porta de DB = `adapters/outbound/db/` (UoW move na Wave 2). **ADR-013 emendada** (catch-all = `ErrorHandlingMiddleware` interno ao CORS). **ADR-016** checklist: parte CI resolvida (`develop` nos gatilhos de push); secret = ação do responsável.

**Testes / cobertura:**
- **Gate de re-verificação (§5) VERDE:** ruff + ruff format + mypy strict; ciclo Alembic `upgrade→downgrade→upgrade` (PostgreSQL 16.9 real, porta 5433); **88 passed, cobertura 100%** (`REQUIRE_DB_TESTS=1`); keep-alive `exit 0`; domínio limpo; varredura de segredos limpa; `pnpm install/lint/format:check/build` verdes; lockfiles versionados.

**Pendências / em aberto:**
- [ ] **W0-A-001 (responsável):** cadastrar `KEEPALIVE_DATABASE_URL` no GitHub (Settings → Secrets and variables → Actions) e validar via `workflow_dispatch`. Até lá o cron diário falha e o Supabase fica desprotegido.
- [ ] **Dívida W0-A-029:** pinar as imagens base do `Dockerfile` por digest ao definir a plataforma de deploy (ADR-009).
- [ ] **W0-A-018:** mover `SqlAlchemyUnitOfWork` para `adapters/outbound/db/` na Wave 2 (C06).
- [ ] (Herdada) `apps/web/public/` untracked (assets do W1-C03); confirmar plataformas de deploy (ADR-009).

**Próximo passo:**
- **Wave 1 · W1-C03 · Tela de Login e Sessão** na branch `develop`.

**Definition of Done:** ✅ Gate verde; correções testadas e aderentes ao `CLAUDE.md`; sem regressão; sem segredos versionados; protocolo de encerramento executado.

---

## Sessão 03 — 2026-06-11 — [Wave 0 / W0-AUDIT] Auditoria read-only da Wave 0

**Objetivo:** Auditoria independente e somente-leitura dos componentes W0-C01 e W0-C02 (escopo de `PROMPTS/W0-AUDIT-auditoria.md`) — inspecionar, verificar e relatar, **sem corrigir nada**.

**Feito:**
- Verificações executáveis contra **PostgreSQL 17.10 real** (binários portáteis, porta 5433; env sobrescrita — Supabase real intocado): ruff + ruff format ✅ · mypy strict ✅ · pytest offline (70 passed/6 skip, 98,81%) ✅ · pytest com `REQUIRE_DB_TESTS=1` (**76 passed, cobertura 100%**) ✅ · ciclo Alembic `upgrade→downgrade→upgrade` em banco limpo ✅ · keep-alive sucesso (`exit 0`) e falha controlada (`exit 1`, sem vazar credencial) ✅ · smoke test da API (`/health` 200, `/health/ready` 503 `degraded` sem R2, `/docs` 200, `X-Request-ID` propagado) ✅ · pnpm lint/build ✅ · varredura de segredos limpa ✅.
- Auditoria multi-agente: 12 auditores por dimensão (§4.1–4.12 + 2 varreduras extras) × verificação adversarial cética de cada achado (48 agentes). 36 achados brutos → **29 únicos** após deduplicação.
- **Relatório entregue:** `docs/audits/wave-0-audit.md` (matriz de conformidade C01 §5/C02 §5/DoD, 29 achados com ID estável `W0-A-001`…`W0-A-029`, lista priorizada de remediação, apêndice de evidências).

**Veredito:** **Wave 0 apta a servir de base à Wave 1 — continuidade NÃO bloqueada.** Contagem: **0 Blocker · 0 High · 2 Medium · 16 Low · 11 Nit**. Os 2 Medium são handoffs operacionais já registrados no ADR-016 e ainda não executados: **W0-A-001** (cron do keep-alive armado na branch padrão **sem** o secret `KEEPALIVE_DATABASE_URL` → falha diária + Supabase real desprotegido, pausa possível ~2026-06-18) e **W0-A-002** (CI não dispara em push para `develop` — o HEAD da branch de integração nunca rodou no CI do GitHub).

**Pendências / em aberto:**
- [ ] Executar a **sessão de remediação da Wave 0** consumindo `docs/audits/wave-0-audit.md` (ordem sugerida no §5 do relatório; começar por W0-A-001/W0-A-002).

**Próximo passo:**
- **Sessão de remediação da Wave 0** consumindo `docs/audits/wave-0-audit.md`. (A Wave 1 / W1-C03 segue na fila após a remediação dos itens Medium.)

**Definition of Done:** N/A (sessão de auditoria — protocolo leve do prompt W0-AUDIT §8: relatório salvo + esta entrada; `CHANGELOG.md`/`DECISIONS.md`/código intocados por regra).

---

## Sessão 02 — 2026-06-11 — [Wave 0 / Componente C02] Cron Job de Keep-Alive

**Objetivo:** Entregar o keep-alive que impede a pausa do Supabase no free tier (>7 dias sem requisições): rotina read-only de *ping*, workflow agendado, alerta de falha e docs — reutilizando a infra do C01 (escopo de `PROMPTS/W0-C02-keep-alive.md`).

**Feito:**
- **Consolidação DRY:** extraída `fetch_db_time()` em `src/infrastructure/database.py` (núcleo único do *ping*, `SELECT now()`); `ping()` do readiness passou a envelopá-la (contrato `-> bool` intacto); novo `create_direct_engine()` para a conexão *one-shot* na direta/sessão (5432).
- **Rotina** `src/tasks/keep_alive.py` (`uv run python -m src.tasks.keep_alive`): conexão curta via `MIGRATIONS_DATABASE_URL`, log JSON estruturado (`event`/`status`/`latency_ms`/`db_time`/`correlation_id`/`env`), exit 0/≠0, erro sem vazar credencial (só `error_type`).
- **Workflow** `.github/workflows/keep-alive.yml`: `schedule 0 9 * * *` (06:00 BRT) + `workflow_dispatch`, `concurrency`, `timeout-minutes: 5`, `permissions: contents: read`, secret `KEEPALIVE_DATABASE_URL`, alerta opcional `if: failure()` + `ALERT_WEBHOOK_URL` (pulado sem o secret).
- **Testes:** offline (`tests/unit/test_keep_alive.py` — campos do log, exit codes, prova de não-vazamento de senha) e `@db` (`tests/integration/test_keep_alive.py` — sucesso real). Fix de hermeticidade do `test_main.py` (`chdir(tmp_path)`) e *fixture* autouse `_isola_logging_global` em `conftest.py`.
- **Docs:** `docs/keep-alive.md` (racional, cadência, ligar em produção, teste manual, alternativa Cloudflare Worker Cron) + link em `docs/setup-infra.md`.
- **Validação em execução real:** *ping* read-only ao **Supabase real** → `exit 0`, `status="ok"`, `db_time` real, `latency_ms≈331ms`; falha com credencial inválida → `exit 1`, `status="error"`, sem vazar a senha.
- Revisão adversarial multi-agente (6 dimensões × verificação cética) sobre o change set.
- **Publicado no GitHub:** repositório [`3studioagn/Sistema-Digital`](https://github.com/3studioagn/Sistema-Digital) criado; remote `origin` configurado; branches `main` (estável) e `develop` (integração, **padrão**) enviadas em `abc293c` via Git Credential Manager (ambiente sem `gh`).

**Decisões (ADRs):**
- **ADR-015** (keep-alive externo; scheduler primário GitHub Actions; conexão direta para o *one-shot*; cadência diária; alerta nativo + webhook opcional; alternativa Cloudflare documentada). **Nota:** o prompt referenciava "ADR-012", mas 012–014 já existiam (W0-C01) → adotado o próximo livre, **015** (divergência registrada, `CLAUDE.md §2.1`).

**Testes / cobertura:**
- **70 passaram, 6 skip** (`@db`, sem Postgres local) offline; cobertura **98.81%** (linhas restantes são caminhos de sucesso `@db`, cobertos no CI). `ruff`, `ruff format` e `mypy --strict` verdes. Sem segredos versionados.

**Pendências / em aberto:**
- [x] Push para o remoto — **feito**: `3studioagn/Sistema-Digital` (branches `main` + `develop`). Resolve também a pendência herdada do C01.
- [ ] **Ligar keep-alive em produção:** cadastrar o secret `KEEPALIVE_DATABASE_URL` (e opcional `ALERT_WEBHOOK_URL`) em **Settings → Secrets and variables → Actions** — o cron diário (06:00) **falha** sem ele; validar via `workflow_dispatch`.
- [ ] **CI em `develop`:** `ci.yml` só dispara em `main` + PRs; pushes diretos em `develop` não acionam a CI. Decidir adicionar `develop` aos gatilhos de push **ou** adotar fluxo por PR (ADR-016).
- [ ] **`apps/web/public/`** (`login-bg.png` 18 MB + `logo-3studio.svg`) untracked — decidir **Git LFS** vs commit normal; pertence ao W1-C03.
- [ ] (Opcional) Branch padrão no GitHub = `develop`; trocar para `main` em Settings → Branches se preferir.
- [ ] (Herdada) Confirmar plataformas de deploy (ADR-009).

**Próximo passo:**
- **Wave 1 · W1-C03 · Tela de Login e Sessão** (primeiro componente da Wave 1; Wave 0 concluída). Trabalhar na branch `develop`.

**Definition of Done:** ✅ atendida no subconjunto aplicável (testes ≥ piso, observabilidade/log estruturado, error handling com exit code + alerta, docs do módulo, sem segredos versionados, idempotência N/A — operação read-only sem escrita).

---

## Sessão 01 — 2026-06-10 — [Wave 0 / Componente C01] Configuração de Infraestrutura

**Objetivo:** Fundação completa do monorepo: backend FastAPI hexagonal, Alembic, storage R2, observabilidade, frontend Next.js, CI e docs de provisionamento (escopo do prompt `PROMPTS/W0-C01-infraestrutura.md`).

**Feito:**
- Monorepo inicializado (git, `.gitignore`, `.editorconfig`, `.gitattributes`, `docker-compose.yml` com Postgres 17 + banco de teste isolado).
- `apps/api`: arquitetura Ports & Adapters completa (config → logging → database → porta de storage → adapter R2 → middleware/erros → health → app factory → composition root). Alembic async + baseline `0001` (pgcrypto) + `migrations/rls/README.md`. Dockerfile multi-stage non-root. `.env.example` integral.
- `apps/web`: Next 16.2.9 (App Router, TS strict, CSS Modules), página de status com consulta única ao readiness, client Supabase mínimo lazy, ESLint+Prettier, build hermético.
- CI GitHub Actions (api: ruff/mypy/alembic↑↓/pytest com Postgres service; web: lint/build) + deploy documentado parametrizável.
- `docs/setup-infra.md` (provisionamento Supabase/R2 + checklist de aceitação).
- Validação contra **PostgreSQL 17.10 real** (binários portáteis, porta 5433): 66 testes verdes com `REQUIRE_DB_TESTS=1`, ciclo `alembic upgrade head → downgrade base → upgrade head` via CLI em banco limpo, API de pé com `/health` 200, `/health/ready` 503 `degraded` (storage down sem R2 — degradação esperada) e `/docs` servindo OpenAPI.
- Revisão adversarial multi-agente (6 dimensões × verificação cética) sobre os critérios de aceitação, regra hexagonal, segredos, escopo, CI e ADR-007.

**Decisões (ADRs):**
- ADR-007 → **Aceita** (validada em execução); ADR-010 → **Aceita** (uv/pnpm confirmados); ADR-003 anotada com as versões pinadas.
- **ADR-012** (porta de storage síncrona + threadpool), **ADR-013** (catch-all no middleware de request-id, envelope canônico de erro), **ADR-014** (Next 16 pinado, build hermético) — novas.

**Testes / cobertura:**
- 66 testes (unit + integração), **100% de cobertura** da camada (piso configurado: 80%). `ruff` e `mypy --strict` verdes. `pnpm lint`/`pnpm build` verdes. Sem warnings na suíte.
- Testes `@db` fazem skip sem Postgres local e FALHAM no CI se o banco sumir (`REQUIRE_DB_TESTS=1`).

**Pendências / em aberto:**
- [x] Provisionar Supabase + R2 — **já existiam** (verificado via MCP em 2026-06-10): projeto `rastreio-provas-digitais` (ref `wmpxxrzbzqgsorjwczvz`, sa-east-1, PG 17, `pgcrypto` instalado) e bucket R2 `rastreio-provas-digitais`. `.env` locais preenchidos com URL e chave publishable.
- [x] Senha do banco preenchida e validada (2026-06-10). Descoberta: conexão direta é IPv6-only → `MIGRATIONS_DATABASE_URL` ajustada para o **session pooler** (aws-1:5432, emenda na ADR-007). `alembic upgrade head` aplicado no Supabase real (`0001 (head)`); **readiness 200 com `database: ok` + `storage: ok`** — infraestrutura real completa.
- [x] API Token do R2 criado e validado (2026-06-10): `storage: ok` no readiness e roundtrip real upload→download→delete via `StoragePort` (roteiro `docs/setup-infra.md` §5) executado com sucesso contra o bucket `rastreio-provas-digitais`.
- [ ] Confirmar plataformas de deploy com o responsável (ADR-009) e ligar os jobs comentados no `ci.yml`.
- [ ] Push para o remoto `rastreio-provas-digitais` quando o repositório for criado no GitHub.

**Próximo passo:**
- **W0-C02 · Cron Job de Keep-Alive** (depende do C01, agora concluído).

**Definition of Done:** ✅ atendida no subconjunto aplicável à infraestrutura (testes ≥ piso, migrations versionadas e aplicáveis, sem erros de console/log crítico, docs por módulo, RLS = política versionada [implementação na W1], observabilidade e error handling validados; itens de UI/animação/N+1 não se aplicam a este componente).

---

## Sessão 00 — 2026-06-09 — Bootstrap do projeto (Engenharia de Prompts)

**Objetivo:** Analisar os documentos de especificação, estabelecer a fundação de contexto e preparar a execução da Wave 0.

**Feito:**
- Análise integral de: Requisitos v1.0, Backlog v1.0, DAT v3.0 e UML v3.0.
- Criação dos documentos de contexto na raiz: `CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`.
- Definição da hierarquia de fontes da verdade e mapeamento das divergências entre as versões dos documentos (`CLAUDE.md §2.1`).
- Consolidação do glossário de domínio canônico (14 estados, 4 rotas, enums) em `CLAUDE.md §6`.
- Baseline de ADRs (001–011) em `DECISIONS.md`.
- Preparação do prompt de execução do **W0-C01 — Configuração de Infraestrutura**.

**Decisões (ADRs):**
- ADR-001 a ADR-006 — Aceitas (monorepo, hexagonal, stack, rota manual/imutável, máquina de estados em código, RBAC em profundidade).
- ADR-007 a ADR-010 — Propostas (conexão Supabase, RLS por request, deploy, gerenciadores de pacote) — a confirmar nas waves indicadas.
- ADR-011 — Aceita (tratamento dos documentos desatualizados; UML a regenerar; DAT §6 ignorado).

**Pendências / em aberto:**
- [ ] Confirmar plataformas de deploy (ADR-009) com o responsável.
- [ ] Validar estratégia de conexão Supabase (pooler de transação + NullPool) em execução (ADR-007, na W0-C01).
- [ ] Regenerar UML alinhado à v1.0 — após a Wave 2.

**Próximo passo:**
- Executar **W0-C01 — Configuração de Infraestrutura** (prompt em `prompts/wave-0/W0-C01-infraestrutura.md`).

**Definition of Done:** N/A (sessão de preparação; nenhum componente de código fechado ainda).
