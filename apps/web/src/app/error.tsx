"use client";

import { useEffect } from "react";

import { reportClientError } from "@/lib/observability/report-error";

import styles from "./error.module.css";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportClientError(error, { boundary: "root", digest: error.digest });
  }, [error]);

  return (
    <div className={styles.page}>
      <main className={styles.card} role="alert">
        <p className={styles.kicker}>Erro</p>
        <h1 className={styles.title}>Algo deu errado</h1>
        <p className={styles.subtitle}>
          Ocorreu um erro inesperado ao renderizar esta página. Tente novamente; se persistir,
          recarregue ou volte mais tarde.
        </p>
        {error.digest ? <p className={styles.digest}>Referência: {error.digest}</p> : null}
        <button type="button" className={styles.retry} onClick={() => reset()}>
          Tentar novamente
        </button>
      </main>
    </div>
  );
}
