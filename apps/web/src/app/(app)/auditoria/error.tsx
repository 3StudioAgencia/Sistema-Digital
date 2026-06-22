"use client";

/**
 * Error boundary da rota de Auditoria (W6-C20 — RNF-014/RNF-016).
 *
 * Falha inesperada de render NUNCA derruba a app (pilar §3.1): mostra um caminho de
 * recuperação (``reset``). Os erros ESPERADOS (403/erro de rede) já são tratados na
 * própria view (estado de erro + retry); este boundary é a rede de segurança.
 */
import styles from "./auditoria.module.css";

export default function AuditoriaError({ reset }: { error: Error; reset: () => void }) {
  return (
    <section className={styles.pagina} aria-label="Erro na auditoria">
      <p className={styles.estadoVazio} role="alert">
        Algo deu errado ao abrir o log de auditoria.{" "}
        <button type="button" className={styles.tentarNovamente} onClick={reset}>
          Tentar novamente
        </button>
      </p>
    </section>
  );
}
