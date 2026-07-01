# Prompt de Execução — W5-C17 · Relatórios Gerenciais com Distribuição por Rota (fiel ao design)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–4 auditadas (GO)**, os **C13 e C16 mergeados**, e as **5 imagens do design anexadas** (Relatórios — abas Geral, 3Studio, Vendedores, Clicheria). Este é o **componente mais amplo do sistema** — leia a §2 (sequenciamento) antes de começar.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (robustez, escalabilidade, **mínimo de requisições ao Supabase**, observabilidade, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–4 entregues):**
- C04: **app shell** (Relatórios é um item da sidebar — visível só ao 3Studio); **fundação de motion**.
- C05: `access-matrix.ts` + middleware + `useAuthorization` + helpers de RLS + claims (ADR-008).
- C06: `provas` (`status`, `rota`, `created_at`, `vendedor_id`, `cliente`, `codigo`); rótulos (módulos C07).
- C07: **listagem com filtros** (status/rota/vendedor/cliente/período) + **URL state** — **reuse os padrões de filtro** (DP-4).
- C11: **`movimentacoes`** (com `ciclo`, motivos de reprovação/cancelamento, timestamps) — a **base histórica** de quase toda métrica temporal. **Reuse — não recrie.**
- C13: timeline — derivou o **caminho canônico** das regras do C11 (útil para "distribuição por rota").
- C16: **dashboard** — criou a **função SQL de horas úteis** e o **padrão de agregação server-side em consulta única**, além do **cálculo de "Atrasadas"**. **Reuse fortemente — C17 não reinventa essas peças.**

**Insumo:** as **5 imagens do design estão anexadas** (há duas iterações: a aba **Geral** em alta fidelidade e as abas **3Studio/Vendedores/Clicheria**) — siga-as (ver §0.2). **Recharts** é a ferramenta de gráficos (já usada no C16).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Este componente tem **muitas métricas**, várias **não especificadas no RF-016** (só no design) e **ambíguas** na definição. Em qualquer ambiguidade — conjunto de métricas, fórmula de uma métrica, base de tempo (horas úteis × corridas), filtros, CSV, sequenciamento, layout — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **leia como o C16 expõe a função de horas úteis e o padrão de agregação**, confirme as Waves 0–4 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas. **DP-1 (sequenciamento), DP-2 (conjunto de métricas) e DP-3 (definições) condicionam todo o resto.**
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** a fórmula de uma métrica nem o significado de um rótulo do design.

---

## 0.2 Fidelidade ao design

**Tela "Relatórios"** (3Studio-only), com um cabeçalho ("Relatórios" + botão **"Exportar CSV"** com caret), **quatro abas** e uma **barra de filtros compartilhada**:
- **Abas:** **Geral** · **3Studio** · **Vendedores** · **Clicheria**.
- **Filtros (compartilhados por todas as abas):** **De / Até** (datas), presets **Hoje / 7d / 30d / 90d**, **Status** (dropdown), **busca** (nome/cliente/nº requerimento), **rota** (Todas / Matriz / Filial), **Vendedor** (dropdown). Um chip de período ativo (ex.: "18/05 – 17/06 · 30 DIAS").
- **Aba Geral:** card preto **"Total geral"** (número + **gráfico de barras** de volume); cards **"Tempo médio aprov."** (horas), **"Taxa reprovação"** (% em vermelho), **"Rota"** (distribuição: Matriz/Filial/Lam. Matriz/Lam. Filial); card **"Provas Ativas"** (**donut** com legenda Reprovada / Aguardando vendedor); card **"Tempo médio de aprovação por vendedor"** (lista ranqueada, horas); card preto **"Vendedor com mais artes"** (nome + número + barras). Abaixo: tabela **"Métricas por Vendedor / Ranking detalhado"** (#, Vendedor, Local, Volume, Aprov., Reprov., Tempo) e tabela **"Provas Atrasadas / Aguardando ação"** (#, Prova, Vendedor, Status, **Atraso** em horas, vermelho).
- **Aba 3Studio:** card preto **"Provas criadas"** (número + média diária); cards **"Reinícios ciclo"**, **"Devolvidas"**, **"Cancel."** (vermelho), **"Reprov. aguardando"** (vermelho), **"Tempo até 1ª mov."** (horas); card **"Top motivos de cancelamento / Diagnóstico do período"** (lista motivo → contagem).
- **Aba Vendedores:** card preto **"Vendedores Filial"** (número + "operando rota direta" + sub-stats Matriz/Ativos/Atrasadas); card **"Ranking por volume / Quem mais movimentou"** (lista ranqueada); tabela **"Detalhamento / Aprovação · Reprovação · Tempo"** (Vendedor, Local, Aprov., Reprov., Tempo, Atras.).
- **Aba Clicheria:** card preto **"Tempo médio aguardando"** (envio → recebimento); cards **"Recebidas no período"**, **"Em trânsito agora"**, **"Origens"**; card **"Provas recebidas por rota de origem / Distribuição"** (com empty state "Nenhuma prova recebida no período"); card **"Fluxo de ciclo / Estado atual"** (Recebidas / Em trânsito / Total origens).

**Os números do design são ilustrativos.** Posições/cards/gráficos/tabelas seguem o design; confirme tokens via Figma (se houver link).

> **Atenção:** o design **amplia muito** o RF-016 (que é *Should*). Ver DP-2 (conjunto de métricas) e DP-3 (definições) — **não** implemente uma fórmula sem confirmá-la.

---

## 1. Objetivo do componente

Entregar a **seção de relatórios gerenciais**, **exclusiva do 3Studio**, **fiel ao design** (quatro abas, filtros compartilhados, gráficos, tabelas, **export CSV**), reusando a **função de horas úteis** e o **padrão de agregação server-side** do C16, com a **distribuição por rota somando 100% no período filtrado** e o **CSV preservando todos os campos exibidos**.

Referências: Backlog **C17** · Requisitos **RF-016 (Should), US-014, RNF-001, RNF-011, RNF-022** · §6 (estados/rotas) · §7 (Relatórios = 3Studio) · C16 (horas úteis + agregação) · C11 (`movimentacoes`) · C07 (filtros).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **RF-016 (Should) — o mínimo obrigatório:** tempo médio de aprovação (**geral e por vendedor**), **total de provas por vendedor**, **quantidade de provas atrasadas**, **total geral**, **taxa de reprovação por vendedor**, **distribuição de provas por rota** (4 rotas), **exportação CSV**. Tudo isso **deve estar presente** (predominantemente nas abas Geral e Vendedores).
2. **Critérios do C17:** relatórios **apenas para 3Studio**; **CSV preserva todos os campos exibidos**; **distribuição por rota soma 100%** considerando as provas do **período filtrado**.
3. **O design amplia o RF-016** com métricas extras (aba 3Studio: reinícios de ciclo, devolvidas, cancelamentos, reprov. aguardando, tempo até 1ª mov., top motivos de cancelamento; aba Clicheria: tempo médio aguardando, recebidas, em trânsito, origens, distribuição por rota de origem, fluxo de ciclo; Geral: provas ativas (donut), vendedor com mais artes). **Essas precisam de definição explícita (DP-3).**
4. **Histórico é a base:** quase toda métrica temporal vem das **`movimentacoes`** (C11) — timestamps de transição, motivos, ciclos.
5. **Acesso (§7):** Relatórios é **exclusivo do 3Studio** — a página inteira (todas as abas) é restrita; **não** há escopo por perfil nos dados (o 3Studio vê tudo).
6. **Performance (RNF-001):** ≤ 3 s; **agregações server-side** (RNF-022), reusando o C16.

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Sequenciamento (LEIA — ver DP-1)
Este componente é **grande**. **Recomendação:** nesta sessão, entregar a **fundação compartilhada** + a **aba Geral**; as abas **3Studio / Vendedores / Clicheria** em **passes seguintes** (cada uma verificável). A §5/§8 abaixo descrevem o componente completo; **a fatia desta sessão depende da resposta da DP-1.**

### Faz parte (fundação + conforme DP-1)
- **Fundação compartilhada:** o **shell de Relatórios** (cabeçalho + tab bar + botão Exportar CSV); a **barra de filtros** (De/Até, presets, Status, busca, rota, Vendedor) com **estado compartilhado** (URL state, reusando padrões do C07) e o **contrato filtros → query**; a **infra de export CSV** (DP-5); a **camada de agregação** reusando a **função de horas úteis** e o padrão do C16 (DP-6); o **controle de acesso 3Studio em duas camadas** (DP-7).
- **Aba Geral** (e demais abas conforme DP-1): os cards/gráficos/tabelas do design (§0.2), cada métrica com a **fórmula confirmada** (DP-3), respeitando os **filtros ativos**.
- **Documentação** (`docs/relatorios.md`): o conjunto de métricas por aba **com as fórmulas**, o contrato de filtros, a estratégia de agregação, o CSV, e o acesso. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Realtime** — relatórios são **snapshots do período filtrado**, recomputados na troca de filtro/aba; **não** são contadores ao vivo (isso é o C16). **Não** abra subscription aqui.
- ❌ **Alteração da máquina de estados / `movimentacoes`** — é do C11 (o relatório **lê**/**agrega**).
- ❌ **Atalhos rápidos** (Componente 18), **log de auditoria** (tela própria do RNF-006) — fora daqui.
- ❌ Métricas **não confirmadas** na DP-3 — **não** invente fórmulas.

> Vontade de adiantar atalhos/auditoria ou introduzir Realtime: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Reuso do C16 (não reinventar):** a **função SQL de horas úteis** e o **padrão de agregação server-side** já existem — **reuse-os**. O cálculo de "Atrasadas" deve ser **consistente** com o do dashboard (mesma regra, mesma fonte).
2. **Agregação por aba, server-side (RNF-022):** **uma consulta de agregação por aba** (não N+1), **lazy-loaded** (compute **só a aba ativa**; não calcule as 4 abas de uma vez), respeitando **todos os filtros ativos**. ≤ 3 s (RNF-001).
3. **Distribuição por rota soma 100%** no período filtrado (critério do C17) — garanta o fechamento (sem provas "perdidas" fora das 4 rotas).
4. **CSV preserva todos os campos exibidos** (critério) e **respeita os filtros ativos** (DP-5).
5. **Base de tempo consistente:** as métricas temporais usam a **mesma base** definida na DP-3 (recomendado: **horas úteis**, seg–sex 07–18 — RNF-011), em todas as abas.
6. **Acesso 3Studio em duas camadas:** middleware/UI **e** validação 3Studio nos endpoints (agregação + export) → **403** caso contrário.
7. **Estilização:** **CSS Modules** **fiel ao design**; **Recharts** para os gráficos (barras, donut); animações `transform`/`opacity` com **`prefers-reduced-motion`**; **responsivo**.
8. **Robustez:** **empty states** (o design os mostra — ex.: "Nenhuma prova recebida no período"); loading/erro por aba; **error boundary**; uma aba que falhe não derruba a tela.
9. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0** (free tier).

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada. **DP-1, DP-2 e DP-3 condicionam o escopo e as fórmulas — são prioritários.**

### Bloco A — Escopo, sequenciamento e definições

**DP-1 — Sequenciamento (componente grande).**
**[Recomendado]** nesta sessão: **fundação compartilhada** (shell, barra de filtros + contrato filtros→query, infra de CSV, reuso de horas úteis + agregação do C16, acesso 3Studio) **+ aba Geral**; abas **3Studio / Vendedores / Clicheria** como **passes seguintes** (cada uma verificável). **Alternativa:** tudo numa sessão. Confirmar.

**DP-2 — Conjunto de métricas por aba (design × RF-016).**
O RF-016 (Should) exige tempo médio aprovação (geral+vendedor), total por vendedor, atrasadas, total geral, taxa reprovação por vendedor, distribuição por rota, CSV — **todos presentes**. O **design adiciona** as métricas extras listadas em §1.1.3. **[Recomendado]** seguir o design (RF-016 é mínimo) e implementar o conjunto completo, **definindo cada métrica extra** (DP-3). Confirmar o **conjunto final por aba**.

**DP-3 — Definições das métricas (ambíguas) — CRÍTICO.**
Confirmar a fórmula de cada uma; **[Recomendado]** abaixo, com **horas úteis** (seg–sex 07–18) como base temporal padrão:
- **Tempo médio de aprovação** (geral e por vendedor): tempo entre **a prova chegar ao vendedor** ("Retirada"/"Encaminhada para o Vendedor") e **"Aprovada pelo Vendedor"**, em **horas úteis**. *(Confirmar a âncora inicial: chegada ao vendedor × criação.)*
- **Taxa de reprovação por vendedor:** reprovadas ÷ (aprovadas + reprovadas) do vendedor, no período. *(Confirmar o denominador.)*
- **Atrasadas:** **mesma regra do C16** (horas úteis no status atual > limiar do C09).
- **Tempo até 1ª mov.** (aba 3Studio): criação → 1ª movimentação, em horas úteis.
- **Tempo médio aguardando** (Clicheria): envio à clicheria → recebimento, em horas úteis.
- **"Devolvidas"** (aba 3Studio): **definição a confirmar** — reprovadas devolvidas ao 3Studio? voltas de laminação? *(Rótulo ambíguo — preciso da definição.)*
- **Provas Ativas** (donut Geral): quais status contam como "ativas" e o **breakdown** (o design mostra Reprovada / Aguardando vendedor). *(Confirmar os segmentos.)*
- **Vendedor com mais artes:** "artes" = **provas**? (contagem de provas por vendedor, top 1). *(Confirmar.)*
- **Reinícios ciclo / Cancelamentos / Reprov. aguardando:** contagens de eventos/estados (de `movimentacoes`/status) no período. **Top motivos de cancelamento:** agregação do **motivo** do C14.
Confirmar todas, em especial **"Devolvidas"**, a **âncora do tempo médio**, o **denominador da taxa**, e a **base horas úteis × corridas**.

### Bloco B — Filtros, CSV, agregação

**DP-4 — Barra de filtros compartilhada + contrato.**
**[Recomendado]** estado de filtro compartilhado (URL state, reusando padrões do C07) que alimenta **todas** as agregações da aba ativa; presets (Hoje/7d/30d/90d) preenchem De/Até. Confirmar: o que **"nº requerimento"** busca (o **código PRV** × um número de requerimento do cliente?), e a precedência preset × De/Até.

**DP-5 — Exportação CSV ("de qualquer relatório").**
Critério: **preserva todos os campos exibidos**; o botão tem **caret**. **[Recomendado]** exportar o **dataset da aba ativa** (todos os campos exibidos), respeitando os **filtros ativos**, com o caret oferecendo opções (por aba/por tabela). Confirmar a granularidade e o tratamento de acentuação/separador (UTF-8 + `;` para Excel pt-BR?).

**DP-6 — Agregação por aba, sem Realtime, reusando o C16.**
**[Recomendado]** **uma consulta de agregação por aba** (server-side, reusando a função de horas úteis + o padrão do C16), **lazy-loaded** (só a aba ativa), respeitando os filtros; **sem Realtime**; ≤ 3 s. Confirmar.

### Bloco C — Acesso, layout, gráficos

**DP-7 — Acesso 3Studio em duas camadas.**
**[Recomendado]** middleware/UI (rota + item de menu escondido para não-3Studio) **e** validação 3Studio nos endpoints de agregação/export → **403** caso contrário. Confirmar.

**DP-8 — Layout, gráficos e mobile (fiel ao design).**
**[Recomendado]** seguir o design (tab bar, barra de filtros, grid de cards por aba, **Recharts**: barras de volume / vendedor-com-mais-artes, **donut** de provas ativas; tabelas Métricas por Vendedor / Provas Atrasadas / Detalhamento; **empty states**; botão Exportar CSV); animações leves + **`prefers-reduced-motion`**; **responsivo**. Confirmar tokens via Figma (se houver link) e o comportamento mobile (tabelas roláveis).

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. A **fatia desta sessão** depende da DP-1. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Backend / Banco — `apps/api/`
- **Agregações por aba** (RNF-022): consultas server-side reusando a **função de horas úteis** e o padrão do C16, **uma por aba**, parametrizadas pelos **filtros** (período, status, rota, vendedor, busca); incluem **distribuição por rota (soma 100%)**, **tempo médio**, **taxa de reprovação**, **atrasadas** (regra do C16), e as métricas extras confirmadas (DP-3).
- **Endpoint(s) de relatório** (Ports & Adapters): retornam os datasets por aba; **validação 3Studio** (DP-7); logs estruturados.
- **Endpoint/serviço de export CSV** (DP-5): gera o CSV do dataset da aba ativa, respeitando filtros, preservando todos os campos; **validação 3Studio**.

### 5.2 Frontend — `apps/web/`
- **Shell de Relatórios** (`app/(app)/relatorios/page.tsx` ou conforme a sidebar) **fiel ao design**: cabeçalho + **tab bar** + **botão Exportar CSV**; **barra de filtros compartilhada** (estado em URL, reusando C07); **lazy-load por aba**.
- **Aba Geral** (e demais conforme DP-1): cards, **gráficos Recharts** (barras, donut), **tabelas** (Métricas por Vendedor, Provas Atrasadas, Detalhamento), **empty states**, loading/erro por aba; animações + `prefers-reduced-motion`; responsivo.
- **Acionamento do CSV** (DP-5) a partir do botão (com opções no caret).

### 5.3 Documentação — `docs/`
- `docs/relatorios.md`: o **conjunto de métricas por aba com as fórmulas** (DP-2/DP-3), o **contrato de filtros** (DP-4), a **estratégia de agregação** (reuso do C16, sem Realtime — DP-6), o **CSV** (DP-5), e o **acesso 3Studio** (DP-7). Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Relatórios disponíveis apenas para 3Studio** (middleware/UI **e** endpoints → 403 para os demais).
2. ✅ Estão presentes **todas** as métricas do **RF-016**: tempo médio de aprovação (geral e por vendedor), total por vendedor, atrasadas, total geral, taxa de reprovação por vendedor, **distribuição por rota**, CSV.
3. ✅ A **distribuição por rota soma 100%** considerando as provas do **período filtrado**.
4. ✅ A **exportação CSV preserva todos os campos exibidos** e respeita os filtros ativos (DP-5).
5. ✅ As métricas respeitam **todos os filtros** (período/preset, status, rota, vendedor, busca) — DP-4; as métricas temporais usam a **base confirmada** (horas úteis — DP-3) e são **consistentes** com o C16.
6. ✅ A tela é **fiel ao design** (4 abas — conforme a fatia da DP-1 —, cards, **gráficos Recharts**, tabelas, empty states, botão Exportar CSV); **agregação por aba lazy-loaded** (não calcula as 4 de uma vez); carrega em **≤ 3 s**.
7. ✅ **Sem Realtime**; animações com **`prefers-reduced-motion`**; responsivo.
8. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; (se migration) `upgrade`/`downgrade` limpa.

---

## 7. Testes desta camada

**Backend**
- Cada agregação com fixtures conhecidas: tempo médio, taxa de reprovação, **distribuição por rota (soma 100%)**, atrasadas (**igual ao C16**), e as métricas extras (DP-3) batem com o cálculo manual.
- **Filtros:** período/preset, status, rota, vendedor, busca alteram corretamente os resultados; combinações.
- **Acesso:** não-3Studio → **403** nos endpoints (mesmo chamando diretamente).
- **CSV:** preserva todos os campos exibidos; respeita filtros; acentuação/separador corretos.
- (Se função/migration) `upgrade`/`downgrade`.
- Roda **offline** (Postgres local; JWT 3Studio; fixtures com histórico em várias rotas/vendedores/tempos).

**Frontend**
- Render **fiel ao design** por aba (cards, gráficos, tabelas, empty states); **lazy-load** (só a aba ativa busca dados); troca de aba/filtro recomputa.
- Botão Exportar CSV dispara o download do dataset filtrado.
- `prefers-reduced-motion`; responsivo (tabelas roláveis no mobile).
- **E2E (Playwright):** como 3Studio, aplicar filtros e ver as métricas mudarem; exportar CSV; como não-3Studio, a tela é inacessível.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, **a função de horas úteis e o padrão de agregação do C16**, e o schema de `movimentacoes` (C11); confirme Waves 0–4 e os padrões de filtro do C07.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas (DP-1/DP-2/DP-3 primeiro).**
3. **Fundação:** shell + tab bar + barra de filtros (estado em URL) + contrato filtros→query; acesso 3Studio (duas camadas); infra de export CSV; camada de agregação reusando o C16.
4. **Aba Geral** (e demais conforme DP-1): agregações server-side (com as fórmulas confirmadas) + UI (cards, Recharts, tabelas, empty states); testes (fórmulas, filtros, soma 100%, CSV, acesso).
5. (Conforme DP-1) abas 3Studio / Vendedores / Clicheria, uma a uma, cada uma verificável.
6. Animações + `prefers-reduced-motion`; responsividade.
7. `docs/relatorios.md`.
8. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
9. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: seção de relatórios (fundação + aba(s) entregue(s)); agregações server-side reusando horas úteis do C16; export CSV; distribuição por rota.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **sequenciamento** (DP-1); (b) **conjunto de métricas por aba** (DP-2); (c) **definições das métricas** (DP-3 — registre **cada fórmula**, é a decisão mais importante); (d) **filtros + nº requerimento** (DP-4); (e) **CSV** (DP-5); (f) **acesso 3Studio** (DP-7). Status *Aceita*.
3. **`SESSION_LOG.md`** — entrada: objetivo, **o que foi entregue (fundação + quais abas)**, decisões (as fórmulas!), testes (citar soma 100%, consistência com o C16, acesso 3Studio), **pendências (abas restantes, se sequenciado)**, e **próximo passo** (a próxima aba, ou **W6-C18 · Atalhos Rápidos** / o que o roadmap indicar).
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre a **camada de agregação de relatórios**, as **fórmulas das métricas**, o **contrato de filtros** e o **export CSV**. Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C17 — fundação/abas concluídas).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **soma 100% da distribuição**, **consistência de atrasadas com o C16**, **acesso 3Studio**, **CSV preserva campos**), (se função/migration) versionada/documentada, agregação por aba lazy-loaded (RNF-022), **sem Realtime**, animações com `prefers-reduced-motion`, sem erro de console/log crítico, docs do módulo, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w5-c17): ...`, `chore(w5-c17): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue (fundação + abas), **evidência de cada critério de aceitação (§6)** (incl. acesso 3Studio, soma 100% da distribuição por rota, CSV preservando campos, e consistência das métricas temporais com o C16), as **fórmulas registradas**, as **pendências (abas restantes)** e o **comando exato** para a próxima sessão.

---

### Lembrete final
Relatório é **decisão de negócio** — e uma métrica com a **fórmula errada** é pior que métrica nenhuma, porque parece confiável e mente. Por isso a parte mais importante deste componente **não é o layout, é a definição de cada número** (DP-3): confirme cada fórmula, use uma **base de tempo consistente** (horas úteis, igual ao C16), e garanta que a **distribuição por rota feche em 100%**. Reuse o que o C16 já construiu (horas úteis, agregação) — não reinvente. E lembre que isto é **snapshot por período**, não dashboard ao vivo: **sem Realtime**. Sendo grande, **sequencie** (DP-1) e entregue cada aba sólida. **Na dúvida — e haverá muitas aqui —, pare e pergunte.** Faça a melhor engenharia possível.
