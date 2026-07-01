"use client";

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
