/**
 * Tokens centralizados de animação (DAT §5.1) — fundação mínima trazida ao
 * W1-C03 (DP-6) para o W1-C19 estender sem reescrever.
 *
 * REGRA: nenhuma animação usa literais inline de duração/easing — só estes
 * tokens (CLAUDE.md §5.5, DAT §5.1). Apenas transform/opacity (GPU, DAT §5.4).
 * Durações em SEGUNDOS (API do Framer Motion).
 */
export const DURATION = {
  instant: 0, // usado quando prefers-reduced-motion = reduce
  micro: 0.15, // hover, focus
  short: 0.25, // toasts, badges
  medium: 0.35, // modais, drawers
  long: 0.5, // page transitions
} as const;

/** Curvas cubic-bezier (formato [x1,y1,x2,y2] aceito pelo Framer Motion). */
export const EASING: Record<"standard" | "emphasized" | "exit", [number, number, number, number]> =
  {
    standard: [0.4, 0.0, 0.2, 1.0], // ease-in-out (Material standard)
    emphasized: [0.2, 0.0, 0.0, 1.0], // ease-out forte (entrada)
    exit: [0.4, 0.0, 1.0, 1.0], // ease-in (saída)
  };

/**
 * Molas (física de microinteração) — extensão do DAT §5.1 para dar uma cara
 * fluida e CONSISTENTE a todas as interações. Reutilizar SEMPRE estas, para que
 * hover/press/parallax tenham o mesmo "peso" em toda a UI (harmonia).
 * - `interactive`: hover/press/realce (quase crítico, sem overshoot perceptível).
 * - `parallax`: seguir o cursor (mais solto, sobreamortecido — sem balanço).
 */
export const SPRING = {
  interactive: { type: "spring" as const, stiffness: 300, damping: 26, mass: 0.6 },
  parallax: { type: "spring" as const, stiffness: 120, damping: 18, mass: 0.4 },
};
