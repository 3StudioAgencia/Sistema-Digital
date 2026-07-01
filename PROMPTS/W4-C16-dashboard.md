# Prompt de Execução — W4-C16 · Dashboard com Contadores em Tempo Real (fiel ao design)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, as **Waves 0–3 auditadas (GO)**, os **C07, C09 e C11 mergeados**, e a **imagem do design anexada** (Dashboard). Este componente **abre a Wave 4** (visibilidade operacional). Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (robustez, escalabilidade, **mínimo de requisições ao Supabase**, observabilidade, animações leves), arquitetura §5 (Ports & Adapters), §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–3 entregues):**
- C04: **app shell** (sidebar + shell branco — o **Dashboard** é o item inicial e ativo); **fundação de motion**.
- C05: `access-matrix.ts` + middleware + `useAuthorization(page) → { hasAccess, scope }` + **helpers de RLS** + propagação de claims (ADR-008).
- C06: `provas` (`status`, `rota`, `created_at`, `vendedor_id`); **rótulos de status** (módulo do C07).
- C07: **listagem com filtros** (status/rota/vendedor/cliente/período) e **URL state** — destino dos **contadores clicáveis** (DP-6).
- C09: **tempo de atraso** (horas úteis, default 48) em `system_settings`, lido **server-side** — o **cálculo de "Atrasadas"** o consome (DP-4).
- C11: **`movimentacoes`** — a **última movimentação** dá o timestamp do último status (base do cálculo de atraso). **Reuse — não recrie.**

**Insumo:** o **design do Figma do Dashboard está anexado** — siga-o (ver §0.2 e as reconciliações da §4). **Recharts** e **Supabase Realtime (WebSocket)** são as ferramentas indicadas (Notas Técnicas do backlog).

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — cobertura de contadores vs. RF-015, mapeamento de status, cálculo de atraso, lista por vendedor, Realtime, atalhos, layout — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **leia como o C09 expõe o tempo de atraso (server-side)** e o schema de `movimentacoes` (C11), confirme o estado das Waves 0–3 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas. **DP-1 (cobertura design × RF-015) é bloqueante.**
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte. **Nunca invente** o mapeamento contador→status, a regra de atraso, nem introduza polling.

---

## 0.2 Fidelidade ao design

**Tela "Dashboard"** (dentro do shell do C04), em **layout bento** (grid de cards), conforme o design:
- Cards de contador (fundo claro, **ícone de documento** no topo-direito) com um **número grande**: **"Criadas hoje"** (ex.: 25), **"Com Vendedor"** (ex.: 6894), **"Aprovadas"** (card mais largo; ex.: 5487), **"Na clicheria"** (ex.: 5).
- **Card "Atrasadas"** (coluna à direita, **alto**): **diferente dos demais** — é uma **lista por vendedor** (nome → contagem: Laine 24, Regiane 43, Regiele 87, Paulinho 54, Diekson 65, Roziane 12, Adriana 21, Tamiris 35, Packon 45, Tiso 12…) com um **total** em destaque ao final (ex.: 258). Rolável quando há muitos vendedores.
- **Botões de atalho** embutidos no grid: **"Escanear QR Code"** (preto, ícone de QR) e **"Nova Prova"** (amarelo).

**Posições/tamanhos dos cards, ícones, tipografia e cores seguem o design.** Confirme tokens via Figma (se houver link). Os **números do design são ilustrativos** (placeholder) — os valores reais vêm das agregações.

> **Atenção (reconciliação obrigatória — DP-1):** o design mostra um **subconjunto** dos contadores do RF-015 e **adiciona atalhos**. Ver §1.1 e DP-1 antes de fixar o conjunto final.

---

## 1. Objetivo do componente

Entregar o **dashboard de visibilidade operacional**, **fiel ao design** (layout bento, "Atrasadas" por vendedor, atalhos), com contadores **em tempo real**, **clicáveis**, **escopados por perfil** (Matriz §7 via RLS), alimentados por **uma única subscription** do Supabase Realtime e por **agregações server-side em consulta única**, com **animação leve de count-up** — reconciliando o design com o RF-015 (DP-1).

Referências: Backlog **C16** · Requisitos **RF-015, RF-017, RF-025, RN-008, RNF-001, RNF-011, RNF-021, RNF-022** · §7 (Dashboard = todos, escopo da listagem) · C09 (tempo de atraso) · C11 (`movimentacoes`) · C07 (listagem).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **RF-015 (Must) pede dois blocos:** **Operação Diária** — Criadas hoje, Com vendedor, Aprovadas, **Reprovadas**, **Concluídas**, Atrasadas; **Em Trânsito** — Com Motorista (ida laminação), (volta laminação), (entrega final). **O design mostra um subconjunto** (Criadas hoje, Com Vendedor, Aprovadas, "Na clicheria", Atrasadas) e **omite "Reprovadas" e todo o bloco "Em Trânsito"**. **Reconciliar em DP-1.**
2. **"Atrasadas" no design = lista por vendedor + total** (não um número único). Ver DP-4.
3. **Atalhos (RF-017):** o design embute **"Escanear QR Code"** e **"Nova Prova"**; RF-017 diz que **os atalhos exibidos respeitam o perfil** (ex.: "Nova Prova" só 3Studio). Ver DP-3.
4. **Clicáveis (RF-015):** clicar num contador **lista as provas daquele status** (DP-6).
5. **Escopo (§7, Dashboard = todos os perfis):** os contadores **respeitam o escopo da listagem** (Vendedor só as suas, Motorista só "Em Trânsito", etc.) — garantido pela **RLS** (claims propagados).
6. **"Atrasada" (RN-008):** prova parada no **mesmo status** além do tempo configurado (C09, default **48 horas úteis**); horário comercial **seg–sex 07–18** (RNF-011). Ver DP-4.
7. **Eficiência (RNF-021/022):** **uma única subscription** do Realtime, **incremental, sem polling nem refetch completo**; **agregações server-side em consulta única** (view/função SQL), sem N+1.
8. **Performance (RNF-001):** carrega em **≤ 3 s** (até 30 usuários). **Animação (RF-025):** **count-up** + transição numérica suave; `prefers-reduced-motion`.

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **Tela de Dashboard** (item inicial do shell do C04) **fiel ao design**: **layout bento** com os cards de contador, o **card "Atrasadas" por vendedor + total**, e os **atalhos** (Escanear, Nova Prova) — com o **conjunto final de contadores reconciliado** (DP-1).
- **Backend — agregação server-side em consulta única** (RNF-022): uma **view/função SQL** (ou consulta única) que retorna **todos** os contadores (incl. o **breakdown de "Atrasadas" por vendedor + total** — DP-4), **executada sob os claims do usuário** (RLS → escopo por perfil).
- **Cálculo de "Atrasadas"** em **horas úteis** (seg–sex 07–18, RNF-011) com o **limiar do C09** (leitura server-side), base na **última movimentação** (DP-4).
- **Realtime:** **uma única subscription** às mudanças de `provas`; ao receber evento, **re-rodar a agregação única** (debounced) — **sem polling**; tratamento do **"Atrasadas"** (time-dependent) na carga + nos eventos (DP-4/DP-5).
- **Contadores clicáveis** → listagem (C07) **pré-filtrada** (URL state), incl. o filtro de **"Atrasadas"** (DP-6).
- **Atalhos role-aware** (DP-3): "Escanear" (todos) → tela de escaneamento (C10); "Nova Prova" (3Studio) → criação (C06).
- **Documentação** (`docs/dashboard.md`): conjunto de contadores reconciliado, a agregação única, o cálculo de atraso, a estratégia de Realtime, o escopo por perfil, e a navegação. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Relatórios gerenciais** (tempo médio, taxa de reprovação, distribuição por rota, CSV) — Componente **17**.
- ❌ **Alteração da máquina de estados / `movimentacoes`** — é do C11 (o dashboard **lê**/**agrega**).
- ❌ **Configuração do tempo de atraso** — é do C09 (o dashboard **consome** o valor).
- ❌ **Polling** de qualquer tipo (proibido por RNF-021 — ver DP-4 para "Atrasadas").

> Vontade de adiantar relatórios ou introduzir polling: **pare** e registre pendência em `SESSION_LOG.md`.

---

## 3. Restrições técnicas (obrigatórias)

1. **Agregação em consulta única (RNF-022):** todos os contadores (incl. o breakdown de "Atrasadas" por vendedor + total) vêm de **uma** consulta server-side (view/função SQL) — **sem N+1**. A consulta roda **sob os claims do usuário** (RLS) para escopar por perfil.
2. **Uma única subscription do Realtime (RNF-021):** **não** crie uma subscription por card; **não** faça polling; **não** refaça refetch completo a cada mudança. Ao receber evento, re-rode a **agregação única** (debounced) ou atualize incrementalmente (DP-5).
3. **"Atrasadas" sem polling (DP-4):** computar na carga + a cada evento do Realtime; a defasagem temporal (provas que "viram" atrasadas sem evento) é **limitada e aceitável** — **não** introduza polling sem decisão explícita.
4. **Cálculo de atraso correto:** horas úteis (**seg–sex 07–18**, RNF-011), limiar do **C09** (server-side), base = última `movimentacao` (ou `created_at`); **feriados fora do escopo** salvo decisão.
5. **Escopo na lista por vendedor:** o breakdown de "Atrasadas" respeita a RLS — para um **Vendedor**, a lista mostra **apenas ele**; para 3Studio/Clicheria, **todos**.
6. **Performance ≤ 3 s** (RNF-001); **mínimo de requisições** (cache/stale-while-revalidate onde fizer sentido — RNF-020).
7. **Estilização:** **CSS Modules** **fiel ao design** (layout bento, ícones, cards, atalhos); **Recharts** se houver visualização gráfica (DP-6); animação `transform`/`opacity` (count-up) com **`prefers-reduced-motion`**; **responsivo** (stack no mobile).
8. **Robustez:** estados de loading/erro; a queda do Realtime **degrada graciosamente** (último valor + reconexão) sem derrubar a tela; **error boundary**.
9. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0** (free tier).

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada. **DP-1 é bloqueante.**

### Bloco A — Reconciliação com o design

**DP-1 — Cobertura de contadores: design × RF-015 (BLOQUEANTE).**
O design mostra **Criadas hoje, Com Vendedor, Aprovadas, Na clicheria, Atrasadas** e **omite "Reprovadas"** e **todo o bloco "Em Trânsito"** (os 3 estados de motorista) — ambos exigidos pelo **RF-015 (Must)**. **[Recomendado]** seguir o **layout do design** e, para honrar o RF-015, **incluir os contadores faltantes ("Reprovadas" + bloco "Em Trânsito") no mesmo estilo visual** (ex.: cards adicionais no grid / um segundo bloco). **Alternativa:** reduzir conscientemente o escopo do dashboard (sem Reprovadas/Em Trânsito), registrando o desvio do RF-015. Confirmar: **complementar** (recomendado) ou **seguir o design exato**.

**DP-2 — Mapeamento dos rótulos do design → status.**
**[Recomendado]** definir explicitamente: **Criadas hoje** (`created_at::date = hoje`); **Com Vendedor** (posse do vendedor — ex.: "Retirada pelo Vendedor" + "Encaminhada para o Vendedor"); **Aprovadas** ("Aprovada pelo Vendedor"); **Atrasadas** (cálculo — DP-4). **Atenção a "Na clicheria"**: diverge do "Concluídas" do RF-015 — é **"Recebida pela Clicheria"** (concluídas/terminal) **ou** "Laminação Concluída" / provas **atualmente** na clicheria? Confirmar **cada** mapeamento, em especial **"Na clicheria"**.

**DP-3 — Atalhos no dashboard (RF-017 + "Nova Prova").**
O design embute **"Escanear QR Code"** e **"Nova Prova"**. **[Recomendado]** renderizá-los **conforme o perfil** (RF-017): "Escanear" para todos → C10; "Nova Prova" só para **3Studio** → C06. Nota: "Nova Prova" **não** consta na lista do RF-017 (escanear/provas/relatórios) e o design **omite** "visualizar provas"/"relatórios" — confirmar o **conjunto exato** de atalhos do dashboard.

### Bloco B — "Atrasadas", cálculo e Realtime

**DP-4 — "Atrasadas" por vendedor + total: cálculo em horas úteis e atualização sem polling.**
O design mostra **Atrasadas agrupadas por vendedor (nome → contagem) + total**. **[Recomendado]** a agregação produz o **breakdown por vendedor + total**, **escopado por RLS** (Vendedor vê só a si; 3Studio/Clicheria todos); o cálculo de "atrasada" é em **horas úteis** (seg–sex 07–18, RNF-011) com o **limiar do C09** (server-side), base na **última movimentação** (ou `created_at`); **feriados fora do escopo**. **Tensão RNF-021:** "atrasada" muda pela **passagem do tempo**, não por evento — **[Recomendado]** computar na carga + a cada evento do Realtime, com **defasagem limitada** (sem polling). Confirmar: o breakdown, a **ordenação** da lista (por contagem desc? alfabética?), o cálculo, e a estratégia sem polling.

**DP-5 — Realtime único + agregação única + escopo.**
**[Recomendado]** **uma única subscription** do Realtime às mudanças de `provas` (RNF-021); **agregação em consulta única** (view/função SQL — RNF-022) **sob os claims do usuário** (RLS → contadores escopados, Matriz §7); ao receber evento, **re-rodar a agregação única** (debounced) — sem polling, sem refetch completo. **Alternativa:** atualização verdadeiramente **incremental** a partir do payload (mais complexa). Confirmar a abordagem.

### Bloco C — Layout, interação, animação

**DP-6 — Layout bento, contadores clicáveis, animação e mobile.**
**[Recomendado]** **bento grid fiel ao design** (posições/tamanhos dos cards, ícones de documento, card "Atrasadas" alto com lista+total, botões Escanear/Nova Prova); **contadores clicáveis** → listagem (C07) **pré-filtrada** (URL state), incl. o **filtro "atrasadas"** (adicioná-lo ao C07, reusando o cálculo) e o **preset "hoje"**; **count-up** + transição suave (RF-025; **`prefers-reduced-motion`**); **responsivo** (stack no mobile — o design é desktop). **Recharts** disponível — confirmar se há gráfico ou só os cards. Confirmar tokens via Figma (se houver link) e o comportamento mobile.

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Backend / Banco — `apps/api/`
- **Agregação em consulta única** (RNF-022): **view/função SQL** retornando **todos** os contadores (conjunto reconciliado — DP-1), **incluindo o breakdown de "Atrasadas" por vendedor + total** (DP-4), **sob RLS** (claims propagados → escopo por perfil). Se exigir uma **função SQL de horas úteis**, criá-la (versionada) com `downgrade`.
- **Endpoint** do dashboard (Ports & Adapters): retorna os contadores + o breakdown (consulta única); claims propagados; logs estruturados.

### 5.2 Frontend — `apps/web/`
- **Tela de Dashboard** (`app/(app)/dashboard/page.tsx` ou conforme a sidebar) **fiel ao design**: layout bento; cards de contador (clicáveis — DP-6); **card "Atrasadas"** com lista por vendedor + total (rolável); **atalhos** role-aware (DP-3); **uma única subscription** do Realtime (DP-5); **count-up** + transição suave; estados de loading/erro; degradação graciosa do Realtime.
- (Se DP-6) extensão do C07 com o **filtro "atrasadas"** (+ preset "hoje"), reusando o cálculo — **sem regredir** os testes do C07.
- (Se DP-6) visualização Recharts; animações `transform`/`opacity`, `prefers-reduced-motion`.

### 5.3 Documentação — `docs/`
- `docs/dashboard.md`: o **conjunto de contadores reconciliado** (design × RF-015), a **agregação única**, o **cálculo de atraso** (horas úteis + limiar do C09), o **breakdown de "Atrasadas" por vendedor**, a **estratégia de Realtime** (subscription única, sem polling), o **escopo por perfil**, e a **navegação** dos cliques. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ O dashboard é **fiel ao design** (layout bento, cards com ícone, **"Atrasadas" como lista por vendedor + total**, atalhos Escanear/Nova Prova), com o **conjunto de contadores reconciliado** (DP-1).
2. ✅ Os contadores refletem dados **em tempo real** com **animação suave** (US-013), via **uma única subscription** do Realtime — **sem polling nem refetch completo** (RNF-021).
3. ✅ As **agregações são computadas server-side em consulta única** (RNF-022), **sem N+1**; carrega em **≤ 3 s** (RNF-001).
4. ✅ Os contadores **respeitam a Matriz §7** por perfil (escopados pela RLS); a **lista de "Atrasadas" por vendedor** respeita o escopo (Vendedor vê só a si).
5. ✅ **"Atrasadas"** computado em **horas úteis** (seg–sex 07–18) com o **limiar do C09**, base na última movimentação; o contador/lista se mantém atual conforme DP-4 (sem polling).
6. ✅ **Clicar num contador lista as provas daquele status** (listagem pré-filtrada, incl. "Atrasadas" — DP-6); **atalhos** navegam conforme o perfil (DP-3).
7. ✅ **Count-up** + transição numérica suave (RF-025) com **`prefers-reduced-motion`**; degradação graciosa do Realtime; **responsivo**.
8. ✅ (Se estendeu o C07) **testes do C07 verdes** (sem regressão).
9. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**; (se migration) `upgrade`/`downgrade` limpa.

---

## 7. Testes desta camada

**Backend**
- A **consulta única** retorna os contadores corretos (conjunto reconciliado) para fixtures conhecidas; **sem N+1**.
- **Breakdown de "Atrasadas" por vendedor + total** correto; **escopo por perfil** (Vendedor só a si; 3Studio/Clicheria todos).
- **"Atrasadas":** função de horas úteis correta (atravessa noite/fim de semana; janela 07–18); parada além do limiar conta; abaixo não; base na última movimentação (ou `created_at`).
- **Escopo por perfil** nos demais contadores (Vendedor só as suas; Motorista só "Em Trânsito"; 3Studio/Clicheria todas).
- (Se função SQL) migration `upgrade`/`downgrade`.
- Roda **offline** (Postgres local; JWTs de teste por perfil; provas via fixture em vários status, vendedores e tempos).

**Frontend**
- Render **fiel ao design** (bento, cards, "Atrasadas" lista+total, atalhos); **count-up** na carga; **uma** subscription (não N); update suave ao chegar evento (mock de Realtime); degradação graciosa se cair.
- Clique num contador → listagem pré-filtrada (incl. "Atrasadas"); atalhos role-aware (Nova Prova oculto para não-3Studio).
- `prefers-reduced-motion` (sem count-up animado); responsivo (stack no mobile).
- **E2E (Playwright):** dashboard como 3Studio (todos os contadores + lista de atrasadas completa + atalho Nova Prova) e como Vendedor (escopo reduzido, atrasadas só dele, sem Nova Prova); clicar num contador → listagem filtrada.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, como o **C09 expõe o tempo de atraso** e o schema de **`movimentacoes`** (C11); confirme Waves 0–3 e a listagem do C07.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas (DP-1 é bloqueante).**
3. Backend: função de **horas úteis** + **agregação em consulta única** (todos os contadores reconciliados + **breakdown de "Atrasadas" por vendedor + total**, sob RLS); endpoint; testes (contadores, breakdown, escopo, atraso, sem N+1).
4. Frontend: dashboard **fiel ao design** (bento, cards clicáveis, card "Atrasadas" lista+total, atalhos role-aware), **uma única subscription** do Realtime, count-up + transição suave, degradação graciosa.
5. (Se DP-6) filtro "atrasadas" + preset "hoje" no C07; re-rodar testes do C07.
6. (Se DP-6) Recharts; `prefers-reduced-motion`; responsividade.
7. `docs/dashboard.md`.
8. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9).
9. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; rode os testes com frequência. Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`: dashboard em tempo real (fiel ao design); agregação server-side em consulta única; breakdown de "Atrasadas" por vendedor; cálculo de atraso (horas úteis); subscription única do Realtime; atalhos; (se aplicável) filtro "atrasadas" no C07.
2. **`DECISIONS.md`** — ADRs conforme as decisões: (a) **reconciliação design × RF-015** (DP-1); (b) **mapeamento contador→status** incl. "Na clicheria" (DP-2); (c) **atalhos role-aware** (DP-3); (d) **"Atrasadas" por vendedor + cálculo + sem polling** (DP-4); (e) **Realtime único + agregação única + escopo** (DP-5). Status *Aceita* onde aplicável; **atualize `CLAUDE.md §2.1`** com a reconciliação do dashboard.
3. **`SESSION_LOG.md`** — entrada: objetivo, feito, **decisões (respostas dos Pontos de Decisão)**, testes (citar escopo por perfil, sem N+1, função de horas úteis, breakdown), **pendências**, e registre que a **Wave 4 (dashboard) está concluída**; **próximo passo** = **W5-C17 · Relatórios Gerenciais com Distribuição por Rota**.
4. **`CLAUDE.md`** — atualize **§9 (comandos)** se necessário; registre a **agregação única do dashboard**, a **função de horas úteis**, o **breakdown de "Atrasadas"**, e a **estratégia de Realtime** (subscription única, sem polling). Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap: **Wave 4 concluída**.
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **escopo por perfil**, **sem N+1**, **cálculo de atraso**, **breakdown por vendedor**), (se migration/função) versionada/documentada, **sem polling** (RNF-021), agregação única (RNF-022), animações com `prefers-reduced-motion`, sem erro de console/log crítico, docs do módulo, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w4-c16): ...`, `chore(w4-c16): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue, **evidência de cada critério de aceitação (§6)** (incl. a fidelidade ao design, a subscription única sem polling, a agregação única escopada, o breakdown de "Atrasadas" por vendedor, e os cliques/atalhos), decisões registradas, o **status da Wave 4** e o **comando exato** para iniciar a próxima sessão (**W5-C17**).

---

### Lembrete final
Este dashboard segue um **design específico** — respeite o **layout bento**, o **card "Atrasadas" como lista por vendedor + total** e os **atalhos** — mas **não** deixe o design apagar um **Must**: o RF-015 pede "Reprovadas" e o bloco "Em Trânsito", ausentes no desenho; **reconcilie conscientemente (DP-1)** antes de seguir. E a engenharia por baixo é o que separa um painel de verdade de um ingênuo: **uma única** subscription do Realtime e **uma única** consulta de agregação (sem polling, sem refetch completo, sem N+1 — cada ida ao Supabase é custo); **"Atrasadas"** que muda pela **passagem do tempo** (resolva sem polling); e contadores que **rodam sob a RLS** (cada perfil vê só os seus números — inclusive a lista de atrasadas por vendedor). **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
