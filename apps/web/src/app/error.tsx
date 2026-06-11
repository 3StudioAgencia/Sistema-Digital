"use client";

import { useEffect } from "react";
import styles from "./error.module.css";

/**
 * Error boundary da rota raiz (App Router) — W0-A-017.
 *
 * Captura erros de renderização (ex.: um corpo de API fora do contrato) e
 * degrada para uma tela amigável com retry, em vez da tela de erro padrão do
 * Next (DoD: "error boundaries cobrindo a rota"; RNF-014/016). Componente de
 * client por exigência do App Router.
 */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Em produção o `digest` correlaciona com o log do servidor.
    console.error(error);
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
