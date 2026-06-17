"use client";

/**
 * AnimatedCounter (W4-C16 / RF-025) — contador com count-up suave.
 *
 * Anima o NÚMERO de 0 → valor na carga e do valor atual → novo valor a cada
 * atualização (eventos Realtime do dashboard). Usa um ``MotionValue`` (não dispara
 * re-render por frame) renderizado como texto — animação de conteúdo, não de
 * layout (não toca width/height/top/left). Respeita ``prefers-reduced-motion``:
 * quando reduzido, salta direto ao valor (degradação instantânea — RNF-010).
 *
 * Componente REUTILIZÁVEL (o C19 generaliza a camada de animação sobre ele).
 */
import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { useEffect } from "react";

import { useReducedMotion } from "@/lib/motion/hooks";
import { DURATION, EASING } from "@/lib/motion/tokens";

export function AnimatedCounter({ value, className }: { value: number; className?: string }) {
  const reduced = useReducedMotion();
  // Começa em 0: SSR/primeiro paint mostram "0" e o count-up sobe a partir daí.
  const mv = useMotionValue(0);
  const texto = useTransform(mv, (v) => String(Math.round(v)));

  useEffect(() => {
    if (reduced) {
      mv.set(value); // instantâneo (sem animação) sob prefers-reduced-motion
      return;
    }
    const controls = animate(mv, value, { duration: DURATION.long, ease: EASING.standard });
    return () => controls.stop();
  }, [value, reduced, mv]);

  // O número final é lido por leitores de tela (aria-label); o texto animado é
  // decorativo (aria-hidden) para não "tagarelar" cada frame.
  return (
    <span className={className} aria-label={String(value)}>
      <motion.span aria-hidden="true">{texto}</motion.span>
    </span>
  );
}
