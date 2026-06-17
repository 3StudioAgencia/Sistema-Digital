"use client";

/**
 * Error boundary da rota de Relatórios (W5-C17 — RNF-014/RNF-016).
 *
 * Falha inesperada de render (ex.: gráfico/aba) NUNCA derruba a app (pilar §3.1):
 * mostra um caminho de recuperação (``reset``). Os erros ESPERADOS por aba
 * (403/erro de rede) já são tratados na própria view (EstadoErro + retry); este
 * boundary é a rede de segurança para o inesperado.
 */
import styles from "./relatorios.module.css";

export default function RelatoriosError({ reset }: { error: Error; reset: () => void }) {
  return (
    <section className={styles.pagina} aria-label="Erro nos relatórios">
      <p className={styles.estadoErro} role="alert">
        Algo deu errado ao abrir os relatórios.{" "}
        <button type="button" className={styles.tentarNovamente} onClick={reset}>
          Tentar novamente
        </button>
      </p>
    </section>
  );
}
