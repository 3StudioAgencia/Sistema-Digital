/**
 * Tokens centralizados de animação (DAT §5.1) — fundação trazida ao W1-C03
 * (DP-6) e consolidada pela camada transversal do W6-C19 (ADR-097..099).
 *
 * REGRA: nenhuma animação usa literais inline de duração/easing — só estes
 * tokens (CLAUDE.md §5.5, DAT §5.1). Apenas transform/opacity (GPU, DAT §5.4).
 * Durações em SEGUNDOS (API do Framer Motion).
 *
 * Faixas dos critérios (Requisitos §RF-023..027):
 *  - page transition (container): `short` (0,25 s) — bem abaixo do teto < 500 ms (RNF-003);
 *  - modais/drawers: `short` (0,25 s) — dentro da faixa 150–300 ms (RF-024);
 *  - toasts/badges/reveal de elementos: `short` (0,25 s) (RF-027);
 *  - count-up de contadores: `long` (0,5 s) (RF-025).
 */
export const DURATION = {
  instant: 0, // usado quando prefers-reduced-motion = reduce
  micro: 0.15, // hover, focus
  short: 0.25, // toasts, badges, modais/drawers (RF-024), reveal de elementos, page transition
  medium: 0.35, // transições maiores (reservado; fora da faixa RF-024 para modais)
  long: 0.5, // count-up dos contadores (RF-025)
} as const;

/** Curvas cubic-bezier (formato [x1,y1,x2,y2] aceito pelo Framer Motion). */
export const EASING: Record<"standard" | "emphasized" | "exit", [number, number, number, number]> =
  {
    standard: [0.4, 0.0, 0.2, 1.0], // ease-in-out (Material standard)
    emphasized: [0.2, 0.0, 0.0, 1.0], // ease-out forte (entrada)
    exit: [0.4, 0.0, 1.0, 1.0], // ease-in (saída)
  };

/**
 * Mola (física de microinteração) — extensão do DAT §5.1 para dar uma cara
 * fluida e CONSISTENTE às interações. Reutilizar SEMPRE em hover/press, para que
 * toda a UI tenha o mesmo "peso" (harmonia). Quase crítica: sem overshoot perceptível.
 */
export const SPRING = {
  interactive: { type: "spring" as const, stiffness: 300, damping: 26, mass: 0.6 },
};

/**
 * Orquestração de entrada em cascata ("elementos surgindo") — W6-C19.
 *
 * `gap` é o atraso entre filhos consecutivos; `maxItens` limita quantos itens de
 * uma lista entram escalonados (os demais aparecem instantâneos) para proteger
 * os ≥ 50 fps em listas grandes (RNF-003). Sob prefers-reduced-motion a cascata
 * é zerada pelo `useReducedMotion()` (tudo aparece de uma vez).
 */
export const STAGGER = {
  gap: 0.04, // 40 ms entre itens
  delayInicial: 0, // sem atraso antes do primeiro item
  maxItens: 12, // teto de itens escalonados em listas longas
} as const;

/**
 * Deslocamento de entrada (em px) usado pelos reveals. Apenas `transform`
 * (`translate`) — nunca `top/left` (CLAUDE.md §11). Pequeno e contido.
 */
export const REVEAL_OFFSET = {
  y: 12, // subir suave (padrão)
  x: 16, // deslizar lateral (ex.: linhas de tabela)
} as const;
