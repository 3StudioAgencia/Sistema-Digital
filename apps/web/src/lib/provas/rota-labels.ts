export type Rota = "matriz" | "lam_matriz" | "filial" | "lam_filial";

export const ROTA_LABELS: Record<Rota, string> = {
  matriz: "Matriz",
  lam_matriz: "Lam. Matriz",
  filial: "Filial",
  lam_filial: "Lam. Filial",
};

export const ROTAS_ORDEM_UI: Rota[] = ["matriz", "filial", "lam_matriz", "lam_filial"];
export function rotuloRota(rota: string): string {
  return ROTA_LABELS[rota as Rota] ?? rota;
}
