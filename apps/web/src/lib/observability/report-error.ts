
export type ErrorContext = {
  boundary?: string;
  digest?: string;
};

export function reportClientError(error: unknown, context: ErrorContext = {}): void {
  console.error("[client-error]", {
    boundary: context.boundary ?? null,
    digest: context.digest ?? null,
    error,
  });
}
