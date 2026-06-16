"use client";

/**
 * Error boundary da rota de confirmação (W3-C12 — RNF-014/RNF-016).
 *
 * Falha isolada (ex.: erro inesperado de render na tela de assinatura) NUNCA
 * derruba a app (pilar §3.1): mostra um caminho de recuperação — recarregar a tela
 * (``reset``) ou voltar ao escaneamento. Os erros ESPERADOS (404/403/422/rede da
 * submissão) já são tratados na própria view com toast + retry; este boundary é a
 * rede de segurança para o inesperado.
 */
import { useRouter } from "next/navigation";

import styles from "./confirmar.module.css";

export default function ConfirmarError({ reset }: { error: Error; reset: () => void }) {
  const router = useRouter();
  return (
    <section className={styles.pagina} aria-label="Erro ao confirmar movimentação">
      <p className={styles.erro} role="alert">
        Algo deu errado ao abrir a confirmação.{" "}
        <button type="button" className={styles.linkRetry} onClick={reset}>
          Tentar novamente
        </button>{" "}
        <button
          type="button"
          className={styles.linkRetry}
          onClick={() => router.replace("/escanear")}
        >
          Voltar ao escaneamento
        </button>
      </p>
    </section>
  );
}
