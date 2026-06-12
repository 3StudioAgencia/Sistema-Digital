/**
 * Sink central de erros do frontend (W1-A-017 / RNF-024, Pilar 5 — Observabilidade).
 *
 * Hoje emite apenas um `console.error` ESTRUTURADO — mas é o ÚNICO ponto de troca
 * para um sink real (Sentry / endpoint de ingest / Worker) quando o provedor for
 * decidido. Essa decisão é de infraestrutura e esbarra na meta de custo R$0
 * (fronteira C19/C20), então fica para depois; o seam garante que LIGAR a captura
 * central seja a mudança de UMA função, não a caçada por `console.error` espalhados.
 *
 * Os error boundaries (`app/error.tsx`, `app/global-error.tsx`, `(app)/error.tsx`)
 * chamam isto em vez de `console.error` cru.
 */
export type ErrorContext = {
  /** Qual boundary capturou (root | global | app). */
  boundary?: string;
  /** `digest` do Next — correlaciona com o log do servidor (Pilar 5). */
  digest?: string;
};

export function reportClientError(error: unknown, context: ErrorContext = {}): void {
  // Forma estruturada para um futuro sink correlacionar com o request_id/digest
  // do backend. Até lá, vai para o console (não quebra o build hermético, sem deps).
  console.error("[client-error]", {
    boundary: context.boundary ?? null,
    digest: context.digest ?? null,
    error,
  });
}
