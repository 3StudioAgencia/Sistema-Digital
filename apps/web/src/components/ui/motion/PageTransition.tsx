"use client";

/**
 * <PageTransition> — transição de página do App Router (RF-023), W6-C19.
 *
 * Extraído do AppShell (ADR-098): faz o fade + leve translateY do CONTAINER da
 * página que entra. Comportamento preservado 1:1 do que já existia inline —
 * enter-only, re-montado a cada navegação pelo `key={pathname}` do chamador
 * (AppShell), sem fase de saída (evita o layout shift de sobreposição RSC).
 *
 * Contenção (CLAUDE.md §3/§11): só `transform`/`opacity` (GPU); duração
 * `short` (0,25 s) << teto < 500 ms do RNF-003; instantâneo sob reduced-motion.
 */
import { motion } from "framer-motion";

import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";

type PageTransitionProps = {
  children: React.ReactNode;
  className?: string;
};

export function PageTransition({ children, className }: PageTransitionProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: reduced ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: reduced ? DURATION.instant : DURATION.short,
        ease: EASING.emphasized,
      }}
    >
      {children}
    </motion.div>
  );
}
