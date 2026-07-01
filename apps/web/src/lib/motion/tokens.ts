export const DURATION = {
  instant: 0, // usado quando prefers-reduced-motion = reduce
  micro: 0.15, // hover, focus
  short: 0.25, // toasts, badges, modais/drawers (RF-024), reveal de elementos, page transition
  medium: 0.35, // transições maiores (reservado; fora da faixa RF-024 para modais)
  long: 0.5, // count-up dos contadores (RF-025)
} as const;

export const EASING: Record<"standard" | "emphasized" | "exit", [number, number, number, number]> =
  {
    standard: [0.4, 0.0, 0.2, 1.0], // ease-in-out (Material standard)
    emphasized: [0.2, 0.0, 0.0, 1.0], // ease-out forte (entrada)
    exit: [0.4, 0.0, 1.0, 1.0], // ease-in (saída)
  };

export const SPRING = {
  interactive: { type: "spring" as const, stiffness: 300, damping: 26, mass: 0.6 },
};

export const STAGGER = {
  gap: 0.04, // 40 ms entre itens
  delayInicial: 0, // sem atraso antes do primeiro item
  maxItens: 12, // teto de itens escalonados em listas longas
} as const;

export const REVEAL_OFFSET = {
  y: 12, // subir suave (padrão)
  x: 16, // deslizar lateral (ex.: linhas de tabela)
} as const;
