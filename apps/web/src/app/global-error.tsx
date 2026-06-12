"use client";

import { useEffect } from "react";

import { reportClientError } from "@/lib/observability/report-error";

/**
 * Global error boundary (App Router) — captura erros lançados no PRÓPRIO
 * `layout.tsx` raiz (que o `error.tsx` não cobre, pois renderiza dentro dele).
 * Substitui `<html>`/`<body>`, então precisa renderizá-los.
 *
 * Estilos INLINE de propósito (exceção justificada à convenção de CSS Modules):
 * este é o boundary de falha catastrófica — deve renderizar uma mensagem usável
 * mesmo que o pipeline de CSS (globals.css/módulos) não tenha carregado. É o
 * padrão recomendado pelo Next para `global-error`.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    reportClientError(error, { boundary: "global", digest: error.digest });
  }, [error]);

  return (
    <html lang="pt-BR">
      <body
        style={{
          fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
          margin: 0,
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#0b1220",
          color: "#e6ebf5",
        }}
      >
        <main style={{ maxWidth: 640, padding: 32, textAlign: "center" }} role="alert">
          <h1 style={{ fontSize: "1.6rem", lineHeight: 1.2, marginBottom: 12 }}>Algo deu errado</h1>
          <p style={{ color: "#9aa7bd", lineHeight: 1.55, marginBottom: 16 }}>
            Ocorreu um erro inesperado ao carregar a aplicação. Tente novamente; se persistir,
            recarregue a página.
          </p>
          {error.digest ? (
            <p
              style={{
                fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace",
                fontSize: "0.8rem",
                color: "#9aa7bd",
                marginBottom: 16,
              }}
            >
              Referência: {error.digest}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => reset()}
            style={{
              font: "inherit",
              cursor: "pointer",
              padding: "8px 16px",
              borderRadius: 8,
              border: "1px solid #24304a",
              background: "#4f8cff",
              color: "#0b1220",
            }}
          >
            Tentar novamente
          </button>
        </main>
      </body>
    </html>
  );
}
