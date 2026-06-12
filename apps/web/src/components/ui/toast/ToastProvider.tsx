"use client";

/**
 * Sistema de toasts reutilizável (W1-C04) — feedback de sucesso/erro.
 *
 * Alinhado ao Toaster do DAT §5.2 (canto inferior direito, slide-in + fade-out
 * automático), que o C19 promove a global definitivo sem reescrever. Apenas
 * transform/opacity; instantâneo sob prefers-reduced-motion (RN-012).
 */
import { AnimatePresence, motion } from "framer-motion";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import { DURATION, EASING } from "@/lib/motion/tokens";
import { useReducedMotion } from "@/lib/motion/hooks";

import styles from "./toast.module.css";

const AUTO_DISMISS_MS = 4000;

type ToastKind = "success" | "error";

type Toast = { id: number; kind: ToastKind; message: string };

type ToastApi = {
  success: (message: string) => void;
  error: (message: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast exige um <ToastProvider> acima na árvore");
  return api;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const reduced = useReducedMotion();

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId.current++;
      setToasts((current) => [...current, { id, kind, message }]);
      // fade-out automático após leitura (DAT §5.2)
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push("success", message),
      error: (message) => push("error", message),
    }),
    [push],
  );

  const duracao = reduced ? DURATION.instant : DURATION.short;

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.region} aria-live="polite" aria-label="Notificações">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.button
              key={toast.id}
              type="button"
              className={`${styles.toast} ${toast.kind === "error" ? styles.error : styles.success}`}
              initial={{ opacity: 0, x: 48 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: duracao, ease: EASING.emphasized }}
              onClick={() => dismiss(toast.id)}
              role="status"
            >
              {toast.message}
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
