/**
 * Variants reutilizáveis da camada transversal de animações (W6-C19).
 *
 * São FÁBRICAS (recebem `reduced`) porque o respeito ao prefers-reduced-motion
 * é centralizado no `useReducedMotion()` (RN-012/RNF-010): quando ativo, toda
 * entrada vira instantânea (duração 0, sem deslocamento, sem cascata).
 *
 * Contenção (CLAUDE.md §3/§11): apenas `transform` (translate/scale) e
 * `opacity` — GPU. Nunca `width/height/top/left`. Durações nos tokens.
 */
import type { Variants } from "framer-motion";

import { DURATION, EASING, REVEAL_OFFSET, STAGGER } from "./tokens";

type RevealOpts = {
  /** Deslocamento vertical inicial (px). Padrão: REVEAL_OFFSET.y. */
  dy?: number;
  /** Deslocamento horizontal inicial (px). Padrão: 0. */
  dx?: number;
  /** Leve escala inicial (ex.: 0.98). Padrão: 1 (sem escala). */
  scale?: number;
  /** Duração da entrada (s). Padrão: DURATION.short. */
  duration?: number;
};

/**
 * Reveal de UM elemento: surge com fade + leve deslocamento (e escala opcional).
 * Estados `hidden`/`show` — combina com a orquestração do container de cascata.
 */
export function fadeRise(reduced: boolean, opts: RevealOpts = {}): Variants {
  const dy = reduced ? 0 : (opts.dy ?? REVEAL_OFFSET.y);
  const dx = reduced ? 0 : (opts.dx ?? 0);
  const scale = reduced ? 1 : (opts.scale ?? 1);
  const duration = reduced ? DURATION.instant : (opts.duration ?? DURATION.short);
  return {
    hidden: { opacity: 0, y: dy, x: dx, scale },
    show: {
      opacity: 1,
      y: 0,
      x: 0,
      scale: 1,
      transition: { duration, ease: EASING.emphasized },
    },
  };
}

type StaggerOpts = {
  /** Atraso entre filhos (s). Padrão: STAGGER.gap. */
  gap?: number;
  /** Atraso antes do primeiro filho (s). Padrão: STAGGER.delayInicial. */
  delayInicial?: number;
};

/**
 * Container de cascata: orquestra a entrada dos filhos em sequência via
 * `staggerChildren`. Sob reduced-motion o gap é 0 (todos surgem juntos).
 */
export function staggerContainer(reduced: boolean, opts: StaggerOpts = {}): Variants {
  const gap = reduced ? 0 : (opts.gap ?? STAGGER.gap);
  const delayChildren = reduced ? 0 : (opts.delayInicial ?? STAGGER.delayInicial);
  return {
    hidden: {},
    show: {
      transition: { staggerChildren: gap, delayChildren },
    },
  };
}
