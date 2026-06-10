"use client";

import { useEffect, useState } from "react";
import styles from "./api-status.module.css";

type CheckResult = "ok" | "down";

type ReadyPayload = {
  status: string;
  checks: { database: CheckResult; storage: CheckResult };
  version: string;
  env: string;
};

type ApiState =
  | { kind: "unconfigured" }
  | { kind: "loading" }
  | { kind: "offline" }
  | { kind: "ready"; payload: ReadyPayload };

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

/**
 * Consulta o readiness da API uma única vez no mount — sem polling, conforme o
 * princípio do mínimo de requisições (RNF-020/021). Degrada com mensagem
 * amigável quando a API não está configurada ou está fora do ar.
 */
export function ApiStatus() {
  const [state, setState] = useState<ApiState>(
    API_BASE_URL ? { kind: "loading" } : { kind: "unconfigured" },
  );

  useEffect(() => {
    if (!API_BASE_URL) return;
    let cancelled = false;

    async function check() {
      try {
        // /health/ready responde 200 ou 503 — ambos trazem o JSON de checks
        const response = await fetch(`${API_BASE_URL}/health/ready`, {
          cache: "no-store",
          signal: AbortSignal.timeout(5000),
        });
        const payload = (await response.json()) as ReadyPayload;
        if (!cancelled) setState({ kind: "ready", payload });
      } catch {
        if (!cancelled) setState({ kind: "offline" });
      }
    }

    void check();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "unconfigured") {
    return (
      <p className={styles.note}>
        API não configurada neste ambiente — defina <code>NEXT_PUBLIC_API_BASE_URL</code> (ver{" "}
        <code>.env.example</code>).
      </p>
    );
  }

  if (state.kind === "loading") {
    return <p className={styles.note}>Consultando a API…</p>;
  }

  if (state.kind === "offline") {
    return (
      <p className={styles.note} role="status">
        <span className={`${styles.dot} ${styles.down}`} aria-hidden /> API inacessível em{" "}
        <code>{API_BASE_URL}</code> — verifique se o backend está de pé (
        <code>uv run uvicorn src.main:app --reload</code>).
      </p>
    );
  }

  const { payload } = state;
  return (
    <section aria-label="Estado da API">
      <h2 className={styles.heading}>
        API <code className={styles.version}>v{payload.version}</code> · ambiente{" "}
        <code>{payload.env}</code>
      </h2>
      <ul className={styles.checks} role="status">
        {Object.entries(payload.checks).map(([name, result]) => (
          <li key={name} className={styles.check}>
            <span
              className={`${styles.dot} ${result === "ok" ? styles.ok : styles.down}`}
              aria-hidden
            />
            <span className={styles.checkName}>{name === "database" ? "Banco" : "Storage"}</span>
            <code className={styles.checkResult}>{result}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}
