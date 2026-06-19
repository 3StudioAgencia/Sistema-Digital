"use client";

/**
 * <Stagger> + <StaggerItem> — cascata de entrada ("elementos surgindo"), W6-C19.
 *
 * O container orquestra os filhos em sequência (`staggerChildren`); cada item
 * surge com fade + leve deslocamento. Os itens HERDAM o disparo do container
 * (não precisam de initial/animate) — por isso devem ser filhos DIRETOS.
 *
 * Uso típico (pilhas verticais de seções/cards onde um wrapper extra é
 * inofensivo). Para layouts sensíveis (grids com seletor `>`, linhas de
 * tabela), aplique as fábricas `staggerContainer`/`fadeRise` diretamente nos
 * elementos existentes (sem DOM extra) — ver lib/motion/variants.ts.
 *
 * Contenção: só `transform`/`opacity` (GPU); instantâneo e sem cascata sob
 * prefers-reduced-motion (gap 0). Em listas longas, escalone só os primeiros
 * STAGGER.maxItens (os demais entram sem variante) para proteger os ≥ 50 fps.
 */
import { motion } from "framer-motion";

import { useReducedMotion } from "@/lib/motion/hooks";
import { fadeRise, staggerContainer } from "@/lib/motion/variants";

type StaggerProps = {
  children: React.ReactNode;
  className?: string;
  /** Atraso entre filhos (s). Padrão: STAGGER.gap. */
  gap?: number;
  /** Atraso antes do primeiro filho (s). Padrão: STAGGER.delayInicial. */
  delayInicial?: number;
};

export function Stagger({ children, className, gap, delayInicial }: StaggerProps) {
  const reduced = useReducedMotion();
  const container = staggerContainer(reduced, { gap, delayInicial });
  return (
    <motion.div className={className} variants={container} initial="hidden" animate="show">
      {children}
    </motion.div>
  );
}

type StaggerItemProps = {
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
};

export function StaggerItem({ children, className, dy, dx, scale, duration }: StaggerItemProps) {
  const reduced = useReducedMotion();
  const item = fadeRise(reduced, { dy, dx, scale, duration });
  return (
    <motion.div className={className} variants={item}>
      {children}
    </motion.div>
  );
}
