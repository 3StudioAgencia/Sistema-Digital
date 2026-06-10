import styles from "./page.module.css";
import { ApiStatus } from "./_components/api-status";

/**
 * Página de status da fundação (W0-C01).
 *
 * Confirma que o build/deploy do frontend está saudável e mostra o estado da
 * API (health checks — RNF-024). As telas de domínio chegam nas waves 1+.
 */
export default function Home() {
  return (
    <div className={styles.page}>
      <main className={styles.card}>
        <p className={styles.kicker}>3Studio</p>
        <h1 className={styles.title}>Rastreio de Provas Digitais</h1>
        <p className={styles.subtitle}>
          Fundação de infraestrutura (Wave 0 · C01) — monorepo, API FastAPI, banco PostgreSQL,
          storage R2 e observabilidade prontos para as próximas waves.
        </p>

        <dl className={styles.meta}>
          <div className={styles.metaItem}>
            <dt>Ambiente do build</dt>
            <dd>{process.env.NODE_ENV}</dd>
          </div>
          <div className={styles.metaItem}>
            <dt>API configurada</dt>
            <dd>{process.env.NEXT_PUBLIC_API_BASE_URL ?? "— (defina NEXT_PUBLIC_API_BASE_URL)"}</dd>
          </div>
        </dl>

        <ApiStatus />
      </main>
    </div>
  );
}
