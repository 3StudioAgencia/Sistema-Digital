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
 * Valida minimamente o shape do corpo antes de tratá-lo como pronto (W0-A-017).
 * Um JSON válido mas fora do contrato (ex.: `{"detail":"Not Found"}` de um
 * NEXT_PUBLIC_API_BASE_URL com path errado, ou um corpo de proxy) passaria pelo
 * cast e quebraria `Object.entries(payload.checks)` na renderização.
 */
function isReadyPayload(value: unknown): value is ReadyPayload {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  const checks = record.checks;
  if (typeof checks !== "object" || checks === null) return false;
  const checksRecord = checks as Record<string, unknown>;
  return (
    typeof record.version === "string" &&
    typeof record.env === "string" &&
    typeof checksRecord.database === "string" &&
    typeof checksRecord.storage === "string"
  );
}

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
        // /health/ready responde 200 (ok) ou 503 (degraded) — ambos trazem o
        // JSON de checks. Qualquer outro status (404 de path errado, 5xx de
        // proxy) ou corpo fora do contrato degrada para "offline" em vez de
        // quebrar a renderização (RNF-014/016).
        const response = await fetch(`${API_BASE_URL}/health/ready`, {
          cache: "no-store",
          signal: AbortSignal.timeout(5000),
        });
        if (!response.ok && response.status !== 503) {
          if (!cancelled) setState({ kind: "offline" });
          return;
        }
        const payload: unknown = await response.json();
        if (!isReadyPayload(payload)) {
          if (!cancelled) setState({ kind: "offline" });
          return;
        }
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
