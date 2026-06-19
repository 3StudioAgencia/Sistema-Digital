"use client";

/**
 * MotionModal — modal animado REUTILIZÁVEL (W1-C04, forward-compatible com o
 * <MotionModal> do C19, que apenas generaliza/documenta — DP-8/ADR-028).
 *
 * Animação conforme DAT §5.2: entrada scale 0.96→1.0 + fade; saída fade;
 * DURATION.short (0,25 s — dentro da faixa 150–300 ms do RF-024; W6-C19/ADR-099)
 * com AnimatePresence mode="wait" (nota técnica §3). Apenas transform/opacity
 * (GPU — DAT §5.4) e degradação para instantâneo com prefers-reduced-motion
 * (RN-012/RNF-010).
 *
 * Acessibilidade: role=dialog + aria-modal, foco inicial no painel, trap de
 * Tab, fecha com ESC e clique no overlay, trava o scroll do body.
 */
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";

import styles from "./modal.module.css";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

type MotionModalProps = {
  open: boolean;
  onClose: () => void;
  /** id do elemento que titula o diálogo (aria-labelledby). */
  labelledBy: string;
  children: React.ReactNode;
  /** Classe extra do painel (dimensões/padding específicos do caso de uso). */
  panelClassName?: string;
};

export function MotionModal({
  open,
  onClose,
  labelledBy,
  children,
  panelClassName,
}: MotionModalProps) {
  const reduced = useReducedMotion();
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Trava o scroll de fundo enquanto o modal está aberto.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      // Trap de foco: Tab circula apenas dentro do painel.
      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  const duracao = reduced ? DURATION.instant : DURATION.short;

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence mode="wait">
      {open && (
        <motion.div
          className={styles.overlay}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: duracao, ease: EASING.standard }}
          onMouseDown={(event) => {
            // mousedown no próprio overlay (não em filhos) fecha o modal
            if (event.target === event.currentTarget) onClose();
          }}
          data-testid="modal-overlay"
        >
          <motion.div
            ref={(node) => {
              panelRef.current = node;
              // foco inicial no painel (uma vez, na montagem)
              if (node && !node.contains(document.activeElement)) node.focus();
            }}
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelledBy}
            tabIndex={-1}
            className={`${styles.panel} ${panelClassName ?? ""}`}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: duracao, ease: EASING.emphasized }}
            onKeyDown={onKeyDown}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
