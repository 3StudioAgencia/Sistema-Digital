import type { Variants } from "framer-motion";

import { DURATION, EASING, REVEAL_OFFSET, STAGGER } from "./tokens";

type RevealOpts = {

  dy?: number;
  dx?: number;
  scale?: number;
  duration?: number;
};

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
  gap?: number;
  delayInicial?: number;
};

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
