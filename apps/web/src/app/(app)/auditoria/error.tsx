"use client";

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
