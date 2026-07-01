# Prompt de Execução — Redesign da Tela de Detalhe da Prova (frontend-only, fora do backlog)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz, os **C08, C13, C14 (e C15) mergeados**, e a **imagem do design anexada** (Detalhe da Prova). **Isto NÃO é um item de backlog** — é uma **troca de layout** da tela de detalhe da prova. **Leia a §0.1 antes de tudo: o escopo é travado.**

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio). Sua tarefa nesta sessão é **trocar o layout (frontend) da tela de detalhe da prova** para o novo design anexado — **sem alterar comportamento e sem tocar em mais nada**.

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (animações leves), arquitetura §5, §9 (comandos), §11 (o que NÃO fazer). Localize a **página de detalhe da prova (C08)** (o componente de frontend + seu CSS Module) — é o **único** alvo desta sessão. Note que essa página **compõe** componentes que **não** são desta sessão: a **timeline (C13)** e a **modal de cancelamento (C14)** (e o botão de **reiniciar ciclo — C15**, quando aplicável).

---

## 0.1 ESCOPO TRAVADO — regra dominante e inegociável

**O escopo desta sessão é EXCLUSIVAMENTE o frontend da própria página de detalhe da prova. Nada mais. Em hipótese nenhuma toque em qualquer outro componente, no backend, em migrations, em RLS, ou em componentes compartilhados — e em especial NÃO altere os internals dos componentes embutidos (timeline C13, modal de cancelamento C14, botão/fluxo de reinício C15).**

- ✅ **Permitido:** editar **apenas** os arquivos de **frontend da própria página de detalhe** (o componente da página + o(s) CSS Module(s) dela), e **posicionar/compor** os componentes embutidos **como eles já são** (sem alterá-los).
- ❌ **Proibido:** alterar **qualquer outro componente/tela**; os **internals** da **timeline (C13)**, da **modal de cancelamento (C14)** ou do **reinício (C15)**; o **backend** (endpoints, serviços, agregações, transição); **migrations/RLS**; **componentes compartilhados/reutilizados** (botões, app shell, wrappers usados por outras telas); a **lógica** de arte/etiqueta/cancelamento/histórico; **adicionar chamadas de API ou busca de dados nova**.
- 🛑 **Se o design parecer exigir QUALQUER coisa fora do frontend desta página** — mexer no C13/C14/C15 por dentro, num componente compartilhado, no backend, ou buscar um dado novo — **PARE IMEDIATAMENTE e pergunte.** **"Parecia necessário" não é justificativa para sair do escopo.**

A **auto-auditoria (§7)** vai **provar via `git diff`** que **somente** os arquivos da página de detalhe mudaram. Qualquer arquivo fora disso (incl. C13/C14/C15) no diff é uma falha da sessão.

---

## 0.2 PRESERVAR O COMPORTAMENTO — re-skin muda pixels, não conduta

A página de detalhe tem um **contrato funcional** (de C08 + os embutidos C13/C14/C15) que **permanece idêntico**. Você troca **aparência**, não comportamento. **Preserve integralmente:**
- A **arte da prova** via **URL pré-assinada** (anti-vazamento do C08) — **sem** URL pública, **sem** nova busca.
- As **ações de etiqueta** ("Vizualizar etiqueta", "Baixar etiqueta") — comportamento atual.
- A ação **"Cancelar prova"** (C14) — **3Studio**, só em estados ativos, abrindo a **modal do C14** (motivo obrigatório, invocando o motor do C11). O **botão** é posicionado pelo layout; a **modal e a lógica são do C14** — **não** as altere.
- O botão **"Reiniciar Ciclo"** (C15) — quando o estado é "Reprovada pelo Vendedor" (3Studio); **renderização condicional preservada** (ver DP-2).
- O **"Histórico de movimentações"**: o **empty state** ("Esta prova ainda não teve movimentações… a timeline fica disponível quando a prova for escaneada pela primeira vez") **e** a **timeline (C13)** quando há movimentações — a **timeline é componente embutido**; você molda a **moldura/colocação**, não os internals dela.
- O **escopo de acesso por perfil** (C08: 3Studio/Clicheria tudo; Vendedor só as suas; Motorista só "Em Trânsito"); o **anti-vazamento de existência**.
- **`prefers-reduced-motion`** e a contenção de animações.

Se uma mudança de layout **forçar** mudança de comportamento ou de um componente embutido, é sinal de que você saiu do escopo — **PARE e pergunte** (§0.1).

---

## 0.3 Fidelidade ao novo design

**Tela de detalhe da prova** (dentro do shell existente), conforme o design:
- **"← Voltar"** (topo, pill).
- **Card superior (claro):**
  - **Título** = nome da prova (ex.: "Mussarela fatiada") + **"Requerimento: {nº}"**.
  - **Grade de metadados** (rótulo + valor): **Cliente** · **Rota** · **Criada em** · **Vendedor** · **Ciclo Atual** · **Status**.
  - **Botões:** **"Vizualizar etiqueta"** (amarelo), **"Baixar etiqueta"** (escuro), **"Cancelar prova"** (contorno) — *condicionais a estado/perfil (DP-2)*.
  - **Imagem da arte** da prova à direita (via URL pré-assinada — DP-3).
- **Card inferior (escuro):**
  - Título **"Histórico de movimentações"**.
  - Quando **sem** movimentações: **empty state** ("Esta prova ainda não teve movimentações." + "A timeline visual fica disponível quando a prova for escaneada pela primeira vez.").
  - Quando **há** movimentações: a **timeline (C13)** embutida (componha-a; **não** altere seus internals).

**Os dados do design são ilustrativos.** Layout/medidas/cores/tipografia seguem o design (confirme tokens via Figma se houver link — DP-4).

---

## 1. Objetivo

Aplicar o **novo layout** à tela de detalhe da prova (frontend), **fiel ao design**, **preservando 100% do comportamento** (arte anti-vazamento, etiqueta, cancelar/reiniciar, histórico/timeline, escopo por perfil), **sem tocar em nada além do frontend desta página** (e **sem** alterar os embutidos C13/C14/C15 por dentro), registrando a mudança nos docs (§9) e validando com **auto-auditoria de não-regressão** (§7).

---

## 2. Escopo e NÃO-escopo (rígido)

### Faz parte desta sessão
- **Re-layout do frontend da página de detalhe** conforme §0.3: card superior (título + requerimento + grade de metadados + botões + arte) e card inferior (moldura do "Histórico de movimentações" + empty state + **colocação** da timeline embutida); botão Voltar.
- **Estilos** (CSS Module **da própria página**) e ajustes de marcação **dentro do componente da página**.
- **Exibição de arte e metadados a partir dos dados que a tela já possui** (DP-3) — **sem** nova busca.
- **Composição** dos embutidos (timeline C13, botão→modal de cancelamento C14, botão de reinício C15) **sem alterá-los**.
- **Atualização dos docs de contexto** (§9) — registrar a mudança mesmo fora do backlog.
- **Auto-auditoria** (§7).

### NÃO faz parte (proibido — §0.1)
- ❌ **Internals da timeline (C13)**, da **modal/lógica de cancelamento (C14)**, do **reinício (C15)**.
- ❌ Qualquer **outro componente/tela**; **backend**, endpoints, **transição**, **migrations**, **RLS**.
- ❌ **Componentes compartilhados/reutilizados** (botão global, shell, wrappers) — afford/estilo **local** à página.
- ❌ **Nova chamada de API / busca de dados**; quebrar o **anti-vazamento** (sem URL pública da arte).
- ❌ **Mudança de comportamento** (etiqueta, cancelar, reiniciar, histórico, escopo de acesso, renderização condicional).
- ❌ **Dependências novas** (salvo triviais e **locais** — em dúvida, **pare e pergunte**).

> Qualquer impulso de "aproveitar para alinhar X em outro lugar" ou "melhorar a timeline ali": **pare** e registre como pendência. **Não** é desta sessão.

---

## 3. Restrições técnicas (obrigatórias)

1. **Contenção total:** mudanças só em **arquivos da página de detalhe**. **Zero** alteração fora disso (incl. C13/C14/C15) — provado por `git diff` (§7).
2. **Comportamento intacto (§0.2):** arte anti-vazamento, etiqueta, cancelar (C14), reiniciar (C15), histórico/timeline (C13), escopo por perfil e renderização condicional **continuam exatamente como antes**.
3. **Compor, não alterar:** os embutidos são **posicionados** pelo novo layout, mas seus **internals não mudam**. Se o encaixe exigir mexer neles → **pare e pergunte**.
4. **Sem nova busca:** arte (URL pré-assinada) e metadados a partir do que a tela **já recebe**; se faltar um campo, **pare e pergunte**.
5. **Sem componente compartilhado:** estilos/afford **locais**.
6. **Estilização:** **CSS Modules**; fiel ao design; **responsivo**; animações `transform`/`opacity` com **`prefers-reduced-motion`**.
7. **Stateless**; **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

**DP-1 — Composição × internals dos embutidos.**
A página **compõe** a timeline (C13) e a modal de cancelamento (C14)/reinício (C15). **[Recomendado]** o redesign **posiciona/estiliza a própria página** (card de metadados, arte, botões, moldura do histórico + empty state) e **compõe** os embutidos **sem alterar seus internals**. **Se o layout parecer exigir mudar o C13/C14/C15 por dentro → PARE e pergunte.** Confirmar a fronteira.

**DP-2 — Botões de ação condicionais (estado/perfil).**
O design mostra Vizualizar etiqueta + Baixar etiqueta + **Cancelar prova** (estado "Aguardando vendedor"). **[Recomendado]** **preservar a renderização condicional**: **Cancelar** (estados ativos, 3Studio — C14); **Reiniciar Ciclo** (estado "Reprovada pelo Vendedor", 3Studio — C15) quando aplicável; **etiqueta** conforme o perfil. O design mostra **uma** variante de estado; a página mantém a lógica para os demais. Confirmar.

**DP-3 — Arte e metadados (sem nova busca, anti-vazamento).**
A arte vem via **URL pré-assinada** (anti-vazamento do C08) e os metadados (Cliente/Rota/Criada em/Vendedor/Ciclo Atual/Status) dos **dados que a tela já tem**. **[Recomendado]** preservar o anti-vazamento (**sem URL pública**) e **não** adicionar busca. **Se um campo exibido não estiver disponível hoje → PARE e pergunte.** Confirmar.

**DP-4 — Empty state, compartilhados e tokens.**
A moldura escura do histórico + o **empty state** fazem parte da página. **[Recomendado]** restilizar a moldura/empty-state **localmente**; **se precisar mexer em componente compartilhado → PARE e pergunte**. Confirmar tokens/medidas via Figma (se houver link); **"Voltar"** e **"Cancelar prova"** preservam o comportamento atual.

---

## 5. Entregáveis

> Em dúvida, **pare e pergunte** (§0.1).

1. **Página de detalhe re-estilizada** (frontend), fiel ao design (§0.3), com **comportamento idêntico** (§0.2), **contida** aos arquivos da própria página, **compondo** os embutidos sem alterá-los.
2. **Atualização dos docs de contexto** (§9) registrando a mudança de layout (fora do backlog).
3. **Relatório da auto-auditoria** (§7) — no resumo final e/ou em `docs/audits/AUTOAUDITORIA-DETALHE-PROVA.md`.

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ A página está **fiel ao design** (Voltar; card claro com título + requerimento + grade de metadados + botões + arte; card escuro "Histórico de movimentações" com empty state / timeline embutida).
2. ✅ **Comportamento idêntico ao anterior**: arte via **URL pré-assinada** (sem URL pública); **etiqueta** (Vizualizar/Baixar); **Cancelar prova** abre a modal do C14 (3Studio, estados ativos); **Reiniciar Ciclo** (C15) quando aplicável; **histórico** mostra empty state / **timeline (C13)** conforme o caso; **escopo por perfil** e **anti-vazamento** preservados.
3. ✅ **Nenhum arquivo fora do frontend da página de detalhe foi alterado** — em especial **nenhuma** mudança nos internals de **C13/C14/C15** (provado por `git diff` — §7).
4. ✅ **Nenhuma nova chamada de API/busca**; **nenhum** componente compartilhado/back tocado; **anti-vazamento** intacto.
5. ✅ **`prefers-reduced-motion`** e **responsivo** preservados.
6. ✅ **Suíte inteira verde, sem regressão**; `pnpm lint`/`build` (e `ruff`/`mypy`/`pytest` — que **não deveriam** ter mudado) **verdes**.

---

## 7. Auto-auditoria de não-regressão (OBRIGATÓRIA — antes do encerramento)

Antes de fechar a sessão, **você mesmo audita** o seu trabalho e **prova** que nada regrediu:

1. **Escopo (git diff):** rode `git status`/`git diff --stat` e **liste os arquivos alterados**. **Todos** devem ser do **frontend da página de detalhe**. **Nenhum** arquivo de **C13/C14/C15**, de outro componente, do backend ou compartilhado pode aparecer. Qualquer arquivo fora do escopo = **falha** → reverta (ou, se acredita ser necessário, **pare e pergunte**).
2. **Comportamento preservado:** rode os **testes existentes** do detalhe (C08) e dos embutidos (C13/C14/C15) — **todos verdes**. Verifique: a arte carrega via URL pré-assinada (sem URL pública); etiqueta funciona; "Cancelar prova" abre a modal do C14 e cancela (em estado ativo, como 3Studio); a timeline aparece quando há movimentações e o empty state quando não; a renderização condicional (Cancelar/Reiniciar por estado/perfil) está correta.
3. **Sem regressão no resto:** rode a **suíte inteira** + `lint`/`build` — **verde**.
4. **Fidelidade ao design:** confira item a item contra o design (§0.3 / §6.1).
5. **Sem novas dependências/chamadas:** confirme que não há nova lib (salvo trivial/local aprovado) nem nova chamada de API; **anti-vazamento intacto**.
6. **Registre o resultado** — relatório (no resumo final e/ou `docs/audits/AUTOAUDITORIA-DETALHE-PROVA.md`) com: a **lista de arquivos alterados** (provando o escopo, e que C13/C14/C15 **não** foram tocados), o **status dos testes/suíte**, e a **confirmação de não-regressão**. Se **qualquer** item falhar, **não feche** — corrija ou **pare e pergunte**.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md`, **localize a página de detalhe (C08)** e entenda o **comportamento atual** (arte/anti-vazamento, etiqueta, e como ela **compõe** C13/C14/C15).
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas.**
3. Re-estilize **apenas** a página: card de metadados + arte + botões; moldura do histórico + empty state + **colocação** da timeline; Voltar — **preservando todo o comportamento** e **sem tocar nos embutidos por dentro**.
4. `prefers-reduced-motion`; responsividade.
5. **Auto-auditoria (§7)** — git diff escopado + testes + suíte + fidelidade.
6. **Atualização dos docs (§9).**
7. Verifique **todos** os critérios de aceitação (§6).

> Em qualquer dúvida que toque algo fora do frontend desta página (incl. os embutidos), **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — atualizar TODOS os docs, mesmo fora do backlog)

Esta mudança **não** é item de backlog, mas **deve ficar registrada** para o projeto seguir alinhado. **Execute e confirme:**

1. **`CHANGELOG.md`** — em `[Unreleased] → Changed`: **redesign do layout da tela de detalhe da prova** (frontend; comportamento inalterado; embutidos C13/C14/C15 não tocados).
2. **`DECISIONS.md`** — **ADR** registrando: a **decisão de trocar o layout** da tela de detalhe (UX fora do backlog), o **escopo travado** (somente frontend dessa página; embutidos compostos, não alterados), e a **confirmação de comportamento preservado**. Inclua as respostas dos Pontos de Decisão (DP-1 fronteira, DP-2 condicionais, DP-3 arte/metadados). Status *Aceita*.
3. **`SESSION_LOG.md`** — entrada: **sessão de redesign frontend da tela de detalhe (fora do backlog)**, o que mudou, as decisões, o **resultado da auto-auditoria** (escopo respeitado + sem regressão + C13/C14/C15 intactos), e que **nenhum outro componente foi tocado**.
4. **`CLAUDE.md`** — se a tela de detalhe é descrita/aludida lá, **atualize** a descrição do layout (mantendo o registro do comportamento e da composição dos embutidos). Enxuto e verdadeiro.
5. **`README.md`** — atualize se houver menção à tela.
6. **Definition of Done** (`CLAUDE.md §8`): comportamento preservado, **auto-auditoria verde**, **git diff escopado** (sem C13/C14/C15), suíte verde, animações com `prefers-reduced-motion`, **anti-vazamento intacto**, sem segredos versionados.
7. **Commits semânticos** — `style(detalhe-prova): novo layout da tela de detalhe` (e `docs: registro do redesign da tela de detalhe`). Árvore limpa, lockfiles commitados. **Use `style`/`refactor`** (não `feat`).

Ao concluir, **apresente um resumo** com: o que mudou no layout, a **evidência de cada critério de aceitação (§6)**, o **relatório da auto-auditoria** (arquivos alterados provando o escopo + C13/C14/C15 intactos + suíte verde), as decisões registradas, e a confirmação de que **nada além do frontend da página de detalhe foi tocado**.

---

### Lembrete final
Como na tela de assinatura, isto é uma **troca de roupa**, não uma cirurgia — e aqui há um agravante: a página de detalhe **veste** outros componentes (a **timeline**, a **modal de cancelamento**, o **reinício**). Você pode **reposicioná-los** no novo layout, mas **não pode mexer por dentro deles** — isso seria sair do escopo e arriscar regressão em telas/fluxos que dependem deles. Dois compromissos: **não saia do frontend desta página** (e, em especial, **não toque no C13/C14/C15**; se o encaixe parecer exigir, **pare e pergunte**); e **não mude o comportamento** (arte anti-vazamento, etiqueta, cancelar, histórico, escopo por perfil — tudo igual). No fim, **prove** com `git diff` que só a página de detalhe mudou e com a suíte verde que nada regrediu. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
