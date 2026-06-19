# Camada transversal de animações (W6-C19)

> Fonte única da política de motion do produto. Implementa RF-023…RF-027, RN-012,
> RNF-003, RNF-010. **Regra de ouro:** animações **leves, contidas e GPU-only**,
> **instantâneas** sob `prefers-reduced-motion`. Esta camada **consolida** o que
> as Waves 0–5 já tinham inline (C04/C13/C14/C15/C16) e **adiciona** as
> _page transitions_ (RF-023) e o vocabulário de _reveal de entrada_ ("elementos
> surgindo em cascata"). Ver ADR-097/098/099.

---

## 1. Princípios (contenção — inegociável)

1. **Só `transform` e `opacity`.** Proibido animar `width/height/top/left/margin`
   (reflow → mata o fps). O "subir/deslizar" é sempre `translateX/Y` (transform).
2. **`prefers-reduced-motion` → instantâneo**, centralizado em
   [`useReducedMotion()`](../apps/web/src/lib/motion/hooks.ts). Nenhuma primitiva
   trata reduced-motion por conta própria — todas recebem o `reduced` do hook.
3. **Durações nos tokens** ([`lib/motion/tokens.ts`](../apps/web/src/lib/motion/tokens.ts)) —
   **nenhum literal de duração/easing inline**.
4. **`AnimatePresence mode="wait"`** nas transições com saída (modais) — evita
   sobreposição/layout shift.
5. **≥ 50 fps** (RNF-003): listas longas escalonam só os primeiros
   `STAGGER.maxItens` itens; o resto entra instantâneo.

---

## 2. Tokens — `lib/motion/tokens.ts`

| Token | Valor | Uso |
| --- | --- | --- |
| `DURATION.instant` | `0` | reduced-motion |
| `DURATION.micro` | `0.15 s` | hover/focus |
| `DURATION.short` | `0.25 s` | **page transition**, **modais/drawers** (RF-024 150–300 ms), toasts, reveal de elementos |
| `DURATION.medium` | `0.35 s` | reservado (fora da faixa RF-024 para modais) |
| `DURATION.long` | `0.5 s` | count-up dos contadores (RF-025) |
| `EASING.standard` | `[0.4,0,0.2,1]` | ease-in-out |
| `EASING.emphasized` | `[0.2,0,0,1]` | entrada (ease-out forte) |
| `EASING.exit` | `[0.4,0,1,1]` | saída |
| `SPRING.interactive` | spring 300/26/0.6 | microinteração (whileTap, indicador da sidebar) |
| `STAGGER.gap` | `0.04 s` | atraso entre filhos da cascata |
| `STAGGER.maxItens` | `12` | teto de itens escalonados em listas longas |
| `REVEAL_OFFSET.y` / `.x` | `12` / `16 px` | deslocamento de entrada (translate) |

---

## 3. `useReducedMotion()` — fonte única (RN-012/RNF-010)

[`lib/motion/hooks.ts`](../apps/web/src/lib/motion/hooks.ts). SSR-safe via
`useSyncExternalStore` (retorna `false` no servidor, reconcilia no 1º paint sem
hydration mismatch). Quando `true`, **toda** animação decorativa vira
`DURATION.instant` (0). É chamado no **topo** do componente, **antes de qualquer
return condicional**.

---

## 4. Variant factories — `lib/motion/variants.ts`

Fábricas que recebem `reduced` (o respeito a reduced-motion mora aqui):

- **`fadeRise(reduced, { dy?, dx?, scale?, duration? })`** → variants `hidden`/`show`
  de **um** elemento (fade + leve deslocamento/escala). Padrão `dy=12`,
  `duration=DURATION.short`. Sob reduced-motion zera deslocamento/escala/duração.
- **`staggerContainer(reduced, { gap?, delayInicial? })`** → variants do
  **container** que orquestra os filhos (`staggerChildren`). Sob reduced-motion o
  gap é 0 (todos surgem juntos).

---

## 5. Primitivas — `components/ui/motion/`

| Primitiva | O quê | Animação |
| --- | --- | --- |
| **`<PageTransition>`** | container da página no App Router (RF-023) | fade + `translateY(8)`, `short`, enter-only |
| **`<Reveal dy? dx? scale? duration? delay?>`** | revela **um** elemento/seção | `fadeRise` |
| **`<Stagger gap? delayInicial?>` + `<StaggerItem dy? dx? scale? duration?>`** | cascata; itens são filhos **diretos** (herdam o disparo) | `staggerContainer` + `fadeRise` |
| **`<MotionModal>`** (`components/ui/modal`) | modal acessível | scale 0.96→1 + fade, **`short` (RF-024)**, `mode="wait"` |
| **`<AnimatedCounter>`** (`components/ui/animated-counter`) | count-up (RF-025) | MotionValue, `long`, preservado do C16 |
| **`ToastProvider`** (`components/ui/toast`) | toasts globais (RF-027) | slide-in (`x`)+fade, **erros ≥ 4 s** |

### Duas técnicas de aplicação por tela

- **(A) Fábricas nos nós existentes** — para **grids com `grid-area`, tabelas,
  flex sensível**: converte o container/itens existentes em `motion.<tag>` com
  `variants={…}`, **sem DOM extra** (preserva o layout). Ex.: dashboard (bento),
  provas/usuários (linhas da tabela).
- **(B) Primitivas** — para **pilhas verticais** onde um wrapper `<div>` é
  inofensivo: `<Stagger>/<StaggerItem>` ou `<Reveal>`. Ex.: escanear, placeholder.

### Page transitions (RF-023)

`<PageTransition>` é renderizado pelo [`AppShell`](../apps/web/src/components/shell/AppShell.tsx)
**com `key={pathname}`** → re-monta a cada navegação (fade + slide, **< 500 ms**,
enter-only, **sem** fase de saída para não conflitar com o streaming do RSC).

---

## 6. Aplicação por tela (reveal de entrada — "sob medida")

| Tela | Tratamento |
| --- | --- |
| Dashboard | cards do bento em cascata (técnica A no grid) — count-up preservado |
| Provas (listagem) | barra de filtros revela; **linhas** deslizam (cap 12) |
| Detalhe da prova | seções em cascata (Voltar → card → histórico); **timeline NÃO re-animada** |
| Relatórios | cabeçalho/abas/filtros/conteúdo em cascata; conteúdo re-cascateia na troca de aba (`key`); contadores preservados |
| Configurações | cards em cascata; `AnimatePresence` interno do card de etiqueta intacto |
| Usuários | toolbar revela; **linhas** em cascata (cap 12) |
| Escanear | seções em cascata (técnica B); **nó do scanner intocado** |
| Nova prova | campos do formulário em cascata (card-reveal preservado) |
| Confirmar | card orquestra; cabeçalho + bloco de assinatura surgem em sequência |
| Placeholder | `<Reveal>` único |

---

## 7. Critérios de aceitação (checklist)

- [x] Page transitions em todas as rotas, **< 500 ms**, fade+slide, GPU-only, sem layout shift (`<PageTransition>` keyed).
- [x] Modais/drawers **150–300 ms** (`DURATION.short`) + `mode="wait"`; toasts slide-in/fade, **erros ≥ 4 s**.
- [x] Count-up (RF-025) e revelação da timeline (RF-026) **preservados**.
- [x] **Toda** animação degrada a instantânea sob `prefers-reduced-motion` (hook central).
- [x] **Nenhuma** animação usa `width/height/top/left`; só `transform`/`opacity`.
- [x] Sem regressão: suíte existente verde; comportamento funcional/visual preservado.

---

## 8. Testes

- Unidade: `lib/motion/variants.test.ts` (contrato das fábricas: faixas e
  reduced-motion), `lib/motion/hooks.test.tsx`, `components/ui/motion/motion.test.tsx`
  (primitivas montam/renderizam em ambos os modos).
- Não-regressão: a suíte das Waves 0–5 (modais, toasts, timeline, dashboard,
  confirmar, detalhe, configurações, sidebar, relatórios) permanece verde.
- Helper compartilhado: **`@/test/motion` → `setReducedMotion(reduce)`**
  (centraliza o mock de `matchMedia`; query-aware).

Comandos: `pnpm test` (vitest), `pnpm lint`, `pnpm build`.
