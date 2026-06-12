"use client";

import { useEffect } from "react";

import { reportClientError } from "@/lib/observability/report-error";

import styles from "../error.module.css";

/**
 * Error boundary do grupo AUTENTICADO `(app)` (W1-A-016).
 *
 * Renderiza DENTRO do `(app)/layout.tsx`, então preserva o app shell (sidebar +
 * navegação) — o usuário recupera no contexto (retry desta seção ou navega por
 * outra), em vez de cair no boundary raiz genérico que substitui o shell inteiro
 * (DoD §8: "error boundaries cobrindo a rota"; RNF-014/016). Reutiliza o estilo
 * do boundary raiz (`../error.module.css`).
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportClientError(error, { boundary: "app", digest: error.digest });
  }, [error]);

  return (
    <div className={styles.page}>
      <main className={styles.card} role="alert">
        <p className={styles.kicker}>Erro</p>
        <h1 className={styles.title}>Algo deu errado</h1>
        <p className={styles.subtitle}>
          Não foi possível carregar esta tela. Tente novamente ou navegue para outra seção pelo
          menu.
        </p>
        {error.digest ? <p className={styles.digest}>Referência: {error.digest}</p> : null}
        <button type="button" className={styles.retry} onClick={() => reset()}>
          Tentar novamente
        </button>
      </main>
    </div>
  );
}
