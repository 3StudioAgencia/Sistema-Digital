/**
 * Rótulos de UI das 4 rotas da prova (W2-C08 / DP-7) — módulo REUTILIZÁVEL,
 * espelhando `status-labels.ts` (C08 detalhe, C13 timeline, C16 dashboard reusam).
 *
 * Os VALORES são os canônicos do `rota_enum` (CLAUDE.md §6 — lowercase),
 * sincronizados 1:1 com `Rota` do backend. O design do detalhe mostrava
 * "Rota direta" (texto legado — NÃO é um dos 4 valores): o detalhe exibe o NOME
 * REAL da rota (RN-007/ADR-004; sem categoria derivada "direta/laminada", que não
 * existe no domínio). Rótulo de UI puro — não toca a Matriz §7 (regra do PR único).
 *
 * `lib/api/provas.ts` re-exporta `Rota`/`ROTA_LABELS`/`ROTAS_ORDEM_UI` daqui para
 * manter os imports existentes (C06/C07) funcionando.
 */

export type Rota = "matriz" | "lam_matriz" | "filial" | "lam_filial";

export const ROTA_LABELS: Record<Rota, string> = {
  matriz: "Matriz",
  lam_matriz: "Lam. Matriz",
  filial: "Filial",
  lam_filial: "Lam. Filial",
};

/** Ordem do segmented control no design: Matriz · Filial · Lam. Matriz · Lam. Filial. */
export const ROTAS_ORDEM_UI: Rota[] = ["matriz", "filial", "lam_matriz", "lam_filial"];

/** Rótulo legível de uma rota; cai no valor cru se vier algo fora do enum. */
export function rotuloRota(rota: string): string {
  return ROTA_LABELS[rota as Rota] ?? rota;
}
