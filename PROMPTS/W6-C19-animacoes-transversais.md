# Prompt de Execução — W6-C19 · Camada Transversal de Animações (Framer Motion)

> **Como usar:** cole este prompt no Claude Code, com os arquivos de contexto (`CLAUDE.md`, `DECISIONS.md`, `CHANGELOG.md`, `README.md`, `SESSION_LOG.md`) na raiz e as **Waves 0–5 auditadas (GO)** (em especial C04, C13, C14, C15, C16 mergeados). Este componente **abre a Wave 6** e é **transversal** — ele toca a aplicação inteira **de propósito**, mas **sem regredir** o que já existe. Trabalhe a sessão inteira nele.

---

## 0. Contexto e autoridade

Você é um engenheiro de software sênior atuando no projeto **Rastreio de Provas Digitais** (3Studio).

**Leia `CLAUDE.md` por inteiro antes de qualquer ação.** Internalize: pilares §3 (**animações leves e suaves, regidas pela contenção**), arquitetura §5, §9 (comandos), §11 (o que NÃO fazer).

**Estado atual do repositório (Waves 0–5 entregues) — animações que JÁ existem (inline):**
- C04: **fundação de motion**; **modais**; **toasts**; tokens iniciais.
- C13: **revelação progressiva da timeline** + destaque da etapa atual (RF-026) — já implementado.
- C14/C15: **modais** de cancelar/reiniciar com animação (RF-024) — já implementados.
- C16: **count-up** dos contadores do dashboard + transição numérica suave no update via Realtime (RF-025) — já implementado.
- Vários componentes já tratam **`prefers-reduced-motion`** individualmente.

**O que falta / o que o C19 consolida:** este componente **estabelece a camada transversal** (tokens, hook central, primitivas reutilizáveis) e **adiciona o principal item novo: as page transitions** (RF-023), que **não** foram feitas por componente. Ver §0.2 (consolidação sem regressão) e DP-1.

**Insumo:** não há "tela" de design — é uma camada de comportamento/motion.

---

## 0.1 Modo de trabalho — PARE E PERGUNTE (regra dominante)

Você **NÃO assume nada por conta própria.** Em qualquer ambiguidade — grau de consolidação, abordagem das page transitions no App Router, tokens, hook — **pare, exponha 2–3 opções e a sua recomendação, e aguarde a resposta** antes de implementar.

1. Antes de escrever **qualquer** código, leia `CLAUDE.md`, **inspecione como as animações existentes (C04/C13/C14/C15/C16) estão implementadas hoje** (inline) e os tokens atuais, confirme o estado das Waves 0–5 e **apresente em bloco todos os Pontos de Decisão da §4.** Aguarde as respostas. **DP-1 (grau de consolidação) condiciona o tamanho da sessão.**
2. Só depois, implemente na ordem da §8.
3. Nova ambiguidade no meio: **pare imediatamente** e pergunte.

---

## 0.2 Transversal SIM — regressão NÃO

Ao contrário de um redesign de tela isolada, o C19 **toca a aplicação inteira de propósito** (é a camada de animações). Mas isso **não** é licença para mudar comportamento:
- **Preserve o comportamento funcional** de **todos** os componentes que você tocar — eles continuam fazendo o que faziam (o dashboard agrega e atualiza igual, a timeline mostra o mesmo, os modais cancelam/reiniciam igual).
- **Preserve (ou melhore sutilmente) o comportamento visual** das animações existentes — count-up, revelação da timeline, modais e toasts **continuam parecendo o que pareciam** (ou ficam mais consistentes), **sem** regressão.
- **Os testes existentes (C13/C14/C15/C16 etc.) são o guarda-corpo:** eles **permanecem verdes**. Se um refactor de consolidação deixar um teste vermelho, ou o componente "fizer algo diferente", **isso é regressão** — corrija ou recue.
- **Refatorar uma animação inline para a primitiva compartilhada NÃO pode alterar a lógica de negócio** do componente. Se parecer que vai, **pare e pergunte** (talvez aquele componente fique fora da consolidação — ver DP-1).

---

## 1. Objetivo do componente

Entregar a **camada transversal de animações** que implementa os **RF-023 a RF-027** de forma **consistente** e **aplicada a toda a aplicação**: **page transitions** (novo), **primitivas reutilizáveis** (`<PageTransition>`, `<MotionModal>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, toasts), **tokens** centrais e um **`useReducedMotion()`** que zera durações — **GPU-only**, **contidas** e **sem regressão** do que já existe.

Referências: Backlog **C19** · Requisitos **RF-023, RF-024, RF-025, RF-026, RF-027, RN-012, RNF-003, RNF-010** · C04 (fundação) · C13/C14/C15/C16 (animações existentes).

---

## 1.1 Fatos do domínio (grounded — não use suposições)

1. **Primitivas da camada (Escopo C19):** `<PageTransition>` (fade + slide leve, envolve cada página do App Router), `<MotionModal>` (scale + fade na entrada, fade na saída), `<AnimatedCounter>` (count-up + transição numérica suave), `<AnimatedTimeline>` (revelação progressiva + destaque da etapa atual), **sistema de toasts global** (slide-in na entrada, fade na saída), `useReducedMotion()` central (zera durações), **tokens** em `/lib/motion/tokens.ts`, **docs** em `/docs/animations.md`.
2. **Durações (critérios):** page transitions **< 500 ms** no total (RNF-003); modais/drawers **150–300 ms** (RF-024); toasts visíveis pelo tempo de leitura, **mínimo 4 s para erros** (RF-027).
3. **prefers-reduced-motion (RN-012, RNF-010):** **toda** animação degrada para **transição instantânea** quando ativo — centralizado no `useReducedMotion()`.
4. **Performance (RNF-003):** **≥ 50 fps** em dispositivos de referência.
5. **Notas técnicas (obrigatórias):** **apenas `transform` e `opacity`** (GPU); **animar `width`/`height`/`top`/`left` é PROIBIDO**; **`AnimatePresence` com `mode="wait"`** para evitar layout shift.
6. **Page transitions (RF-023):** fade + slide leve, **App Router + Framer Motion** — é o **item novo** (não feito por componente).

---

## 2. Escopo e NÃO-escopo (limites rígidos)

### Faz parte desta sessão
- **`/lib/motion/tokens.ts`** — tokens de **duração** e **easing** centrais (consolidando os do C04).
- **`useReducedMotion()`** central — hook que **zera durações** quando `prefers-reduced-motion` está ativo; **fonte única** dessa lógica.
- **`<PageTransition>`** (novo) — envolve cada página do App Router (fade + slide leve, **< 500 ms**, **≥ 50 fps**, **GPU-only**, `AnimatePresence mode="wait"`), instantâneo sob reduced-motion (DP-2).
- **Primitivas reutilizáveis** `<MotionModal>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, **toasts global** — **consolidando** o que existe (DP-1), preservando o comportamento visual/funcional.
- **Refactor dos componentes existentes** para usar a camada **conforme o grau definido na DP-1**, **sem regressão** (testes existentes verdes).
- **`/docs/animations.md`** — os tokens, as primitivas, o uso, e a regra de contenção + reduced-motion. **Testes** (§7) e **Encerramento** (§9).

### NÃO faz parte desta sessão (não implemente agora)
- ❌ **Mudar a lógica de negócio** de qualquer componente (agregações, máquina de estados, RLS, etc.) — o C19 mexe **só** em motion/apresentação.
- ❌ **Animações chamativas** ou que violem a contenção (nada de width/height/top/left; nada de durações longas).
- ❌ **Interface de Log de Auditoria** (Componente **20**).
- ❌ **Redesenhar** telas (layout) — o C19 é **comportamento de animação**, não layout.

> Vontade de "melhorar" o layout/lógica de um componente ao consolidar a animação dele: **pare** e registre pendência. O C19 anima; não redesenha nem altera regra.

---

## 3. Restrições técnicas (obrigatórias)

1. **GPU-only:** **apenas `transform` e `opacity`**. **Proibido** animar `width`/`height`/`top`/`left` (causa reflow e mata o fps).
2. **`AnimatePresence` com `mode="wait"`** nas transições com saída (page transitions, modais) — evita layout shift e sobreposição.
3. **Durações dos critérios:** page < 500 ms; modais 150–300 ms; toasts de erro ≥ 4 s. Centralize nos **tokens**.
4. **reduced-motion centralizado:** **todas** as primitivas consultam o **`useReducedMotion()`** → instantâneo quando ativo. **Não** deixe handling de reduced-motion espalhado e divergente.
5. **Preservar comportamento (§0.2):** funcional **e** visual; **testes existentes verdes**; refactor não altera lógica.
6. **App Router:** as page transitions não podem quebrar **SSR/hydration**, navegação, nem o estado de URL (filtros do C07, etc.) — DP-2.
7. **Performance ≥ 50 fps:** sem jank perceptível; cuidado com re-renders e listas grandes.
8. **Stateless** (RNF-018); **sem segredos versionados**; **R$ 0**.

---

## 4. Pontos de Decisão — apresente em bloco e aguarde resposta (ANTES de codificar)

Apresente todos de uma vez, com a recomendação destacada. **DP-1 condiciona o tamanho da sessão.**

### Bloco A — Estratégia de consolidação (a decisão central)

**DP-1 — Grau de consolidação dos animações existentes.**
As primitivas `<AnimatedCounter>` (C16), `<AnimatedTimeline>` (C13), `<MotionModal>` (C14/C15/C04) e os toasts (C04) **já existem inline**. **[Recomendado]** estabelecer a **camada compartilhada** (tokens, `useReducedMotion()`, primitivas) **e refatorar os existentes para usá-la, preservando comportamento visual/funcional** (guardado pelos **testes existentes** + paridade visual); **se algum refactor arriscar regressão, alinhar apenas aos tokens** e deixar a animação onde está. **Alternativa:** **somente aditivo** (adicionar `<PageTransition>` + tokens + hook; deixar os existentes como estão e consolidar só o trivial). Confirmar o **grau de consolidação** (e, se sequenciar, o que entra nesta sessão).

### Bloco B — Page transitions (o novo principal)

**DP-2 — `<PageTransition>` no App Router.**
**[Recomendado]** envolver cada página com **fade + slide leve** via **`template.tsx`** (re-monta a cada navegação) **ou** um wrapper client keyed em `usePathname`, com **`AnimatePresence mode="wait"`** (nota técnica), **< 500 ms**, **≥ 50 fps**, **GPU-only**, **instantâneo** sob reduced-motion. Confirmar a **abordagem** (`template.tsx` × wrapper) e validar que **não quebra SSR/hydration, navegação, nem o URL-state** (ex.: filtros do C07/relatórios).

### Bloco C — Tokens, hook e toasts

**DP-3 — Tokens + `useReducedMotion()` central + toasts.**
**[Recomendado]** tokens de duração/easing em **`/lib/motion/tokens.ts`** (consolidando o C04); **`useReducedMotion()`** central que **zera durações**; **toasts global** (RF-027) com **slide-in/fade** e **mín. 4 s para erros** — alinhar os toasts do C04 à primitiva. Confirmar (e se os toasts existentes do C04 já atendem o RF-027 ou precisam de ajuste).

---

## 5. Entregáveis detalhados

> Caminhos são o **alvo**; nomes idiomáticos coerentes com `CLAUDE.md §5.1`. A **fatia desta sessão** depende da DP-1. Em dúvida, **pare e pergunte** (§0.1).

### 5.1 Frontend — `apps/web/`
- **`/lib/motion/tokens.ts`** (duração/easing) e **`useReducedMotion()`** central.
- **`<PageTransition>`** integrado ao App Router (DP-2).
- **Primitivas** `<MotionModal>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, **toasts global** — consolidando o existente (DP-1).
- **Refactor** dos componentes (C13/C14/C15/C16…) para usarem a camada **conforme a DP-1**, **sem regressão**.

### 5.2 Documentação — `docs/`
- **`/docs/animations.md`**: os **tokens**, as **primitivas** (uso e props), a **regra de contenção** (GPU-only, durações, `mode="wait"`), e o **reduced-motion** centralizado. Incluir a **checklist** dos critérios (§6).

---

## 6. Critérios de aceitação (devem ser demonstráveis)

1. ✅ **Page transitions em todas as rotas**, duração total **< 500 ms** (RNF-003), fade + slide leve, **GPU-only**, sem layout shift (`mode="wait"`).
2. ✅ **Modais/drawers** na faixa **150–300 ms** (RF-024); **toasts** com slide-in/fade e **≥ 4 s para erros** (RF-027).
3. ✅ **Contadores** transitam com animação suave a cada update via Realtime (RF-025) — **preservado** do C16; **timeline** com revelação progressiva + destaque (RF-026) — **preservado** do C13.
4. ✅ **Toda** animação degrada para **instantânea** com `prefers-reduced-motion` (RN-012, RNF-010), via o **hook central**.
5. ✅ **≥ 50 fps** em dispositivos de referência (RNF-003); **nenhuma** animação usa `width`/`height`/`top`/`left`.
6. ✅ **Sem regressão:** o comportamento funcional e visual dos componentes consolidados é preservado; **a suíte existente (C13/C14/C15/C16 etc.) permanece verde**.
7. ✅ **Stateless**; **sem segredos versionados**; **R$ 0**; `ruff`/`mypy --strict`/`pytest`/`pnpm lint`/`build` **verdes**.

---

## 7. Testes e verificação desta camada

**Animação / unidade**
- `useReducedMotion()` zera durações quando ativo; os tokens são a fonte única.
- `<PageTransition>`: monta/desmonta com `mode="wait"`; reduced-motion → instantâneo; não quebra navegação/URL-state.
- `<MotionModal>`/`<AnimatedCounter>`/`<AnimatedTimeline>`/toasts: durações nas faixas; reduced-motion → instantâneo.

**Não-regressão (guarda-corpo)**
- **Rode a suíte inteira** — os testes de **C13/C14/C15/C16** (e demais) **permanecem verdes** após a consolidação.
- **Paridade visual:** confirme (manual ou por teste) que count-up, revelação da timeline, modais e toasts **continuam parecendo o que pareciam** (ou mais consistentes), **sem** mudança de comportamento.
- **Lógica intacta:** os componentes consolidados **fazem o mesmo** (dashboard agrega/atualiza igual, modais cancelam/reiniciam igual).

**Performance / acessibilidade**
- Sanidade de **fps** nas page transitions (sem jank); **GPU-only** confirmado (sem props de layout animadas).
- Navegação com reduced-motion ativo em todo o app.

**E2E (Playwright)**
- Navegar entre rotas com a transição ativa (e com reduced-motion); abrir um modal; ver um toast — tudo coerente e sem quebra.

---

## 8. Ordem de execução sugerida

1. Leia `CLAUDE.md` e **inspecione as animações inline existentes** (C04/C13/C14/C15/C16) e os tokens atuais; confirme Waves 0–5.
2. **Apresente em bloco os Pontos de Decisão (§4) e aguarde as respostas (DP-1 primeiro).**
3. Camada base: **tokens** + **`useReducedMotion()`** central; testes.
4. **`<PageTransition>`** no App Router (DP-2); validar navegação/URL-state/SSR; reduced-motion.
5. Primitivas (`<MotionModal>`, `<AnimatedCounter>`, `<AnimatedTimeline>`, toasts) + **consolidação** conforme DP-1, **rodando a suíte a cada componente tocado** (guarda-corpo).
6. `/docs/animations.md`.
7. Verifique **todos** os critérios de aceitação (§6) e a sub-checklist da DoD (§9), incl. a **não-regressão**.
8. Execute o **Protocolo de Encerramento** (§9).

> Incrementos pequenos e verificáveis; **rode a suíte com frequência** (a consolidação é onde mora o risco de regressão). Em qualquer dúvida nova, **pare e pergunte** (§0.1).

---

## 9. Encerramento de sessão (OBRIGATÓRIO — `CLAUDE.md §10`)

Antes de finalizar, **execute e confirme**:

1. **`CHANGELOG.md`** — em `[Unreleased] → Added`/`Changed`: camada transversal de animações (tokens, `useReducedMotion()`, `<PageTransition>` novo, primitivas consolidadas), com nota de **comportamento preservado**.
2. **`DECISIONS.md`** — ADRs: (a) **grau de consolidação** (DP-1); (b) **abordagem das page transitions no App Router** (DP-2); (c) **tokens + reduced-motion central + toasts** (DP-3). Status *Aceita*.
3. **`SESSION_LOG.md`** — entrada: objetivo, **o que foi consolidado/adicionado**, decisões, **resultado da não-regressão** (suíte verde + paridade visual), **pendências** (se sequenciado), e **próximo passo** = **W6-C20 · Interface de Log de Auditoria**.
4. **`CLAUDE.md`** — registre a **camada de motion** (tokens, hook, primitivas, page transitions) e a **regra de contenção** (GPU-only, `mode="wait"`, reduced-motion central). Enxuto e verdadeiro.
5. **`README.md`** — atualize o roadmap (C19 concluído).
6. Verifique a **Definition of Done** (`CLAUDE.md §8`): testes (incl. **não-regressão da suíte existente**, reduced-motion central, durações nas faixas), **GPU-only** (sem props de layout animadas), sem erro de console/log crítico, `/docs/animations.md`, **sem segredos versionados**.
7. **Commits semânticos** (`feat(w6-c19): camada de animações`, `refactor(w6-c19): consolida animações existentes`, `chore(w6-c19): ...`), árvore limpa, lockfiles commitados.

Ao concluir, **apresente um resumo** com: o que foi entregue (page transitions + primitivas + tokens + hook), **evidência de cada critério (§6)** (incl. durações, reduced-motion instantâneo, GPU-only, e a **suíte existente verde**/paridade visual), decisões registradas, pendências e o **comando exato** para a próxima sessão (**W6-C20**).

---

### Lembrete final
Esta camada é o "verniz" que faz o produto **parecer profissional** — e a contenção é a regra: **só `transform` e `opacity`**, durações curtas, `mode="wait"`, e **tudo instantâneo** sob `prefers-reduced-motion` (de um único hook). O risco real aqui não é a animação nova (as page transitions) — é a **consolidação**: ao trocar uma animação inline pela primitiva compartilhada, é fácil **mudar sem querer** o que o componente fazia. Por isso os **testes existentes são o guarda-corpo** e a **paridade visual** é critério: o dashboard, a timeline e os modais têm que continuar **fazendo e parecendo** o que faziam. Transversal **não** é desculpa para regredir. **Na dúvida, pare e pergunte.** Faça a melhor engenharia possível.
