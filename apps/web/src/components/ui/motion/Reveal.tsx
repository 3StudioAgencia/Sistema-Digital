"use client";

/**
 * <Reveal> — revela UM elemento/seção ao montar (fade + leve deslocamento),
 * W6-C19. Para títulos, cards isolados e seções que não fazem parte de uma
 * cascata. Para vários filhos em sequência, use <Stagger>/<StaggerItem>.
 *
 * Contenção: só `transform`/`opacity` (GPU); duração nos tokens; instantâneo
 * sob prefers-reduced-motion (via `useReducedMotion()`, fonte única RN-012).
 */
import { motion } from "framer-motion";

import { useReducedMotion } from "@/lib/motion/hooks";
import { fadeRise } from "@/lib/motion/variants";

type RevealProps = {
  children: React.ReactNode;
  className?: string;
  /** Deslocamento vertical inicial (px). Padrão: REVEAL_OFFSET.y. */
  dy?: number;
  /** Deslocamento horizontal inicial (px). Padrão: 0. */
  dx?: number;
  /** Leve escala inicial (ex.: 0.98). Padrão: 1 (sem escala). */
  scale?: number;
  /** Duração da entrada (s). Padrão: DURATION.short. */
  duration?: number;
  /** Atraso antes de revelar (s). Padrão: 0. Zerado sob reduced-motion. */
  delay?: number;
};

export function Reveal({ children, className, dy, dx, scale, duration, delay = 0 }: RevealProps) {
  const reduced = useReducedMotion();
  const variants = fadeRise(reduced, { dy, dx, scale, duration });
  return (
    <motion.div
      className={className}
      variants={variants}
      initial="hidden"
      animate="show"
      transition={{ delay: reduced ? 0 : delay }}
    >
      {children}
    </motion.div>
  );
}
