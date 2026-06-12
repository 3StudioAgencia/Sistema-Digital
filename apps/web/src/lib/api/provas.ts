/**
 * Tipos e operações do recurso /provas (W2-C06).
 *
 * Espelho 1:1 dos schemas do backend (apps/api .../http/provas.py). Os VALORES
 * dos enums são os canônicos do glossário (CLAUDE.md §6 — lowercase); rótulos
 * de UI em ROTA_LABELS. A criação é multipart (arte JPG/PNG ≤ 10 MB — RF-001)
 * e a etiqueta chega como PDF binário gerado sob demanda (DP-7).
 */
import { apiFetch, apiFetchBlob } from "./client";

export type Rota = "matriz" | "lam_matriz" | "filial" | "lam_filial";

export const ROTA_LABELS: Record<Rota, string> = {
  matriz: "Matriz",
  lam_matriz: "Lam. Matriz",
  filial: "Filial",
  lam_filial: "Lam. Filial",
};

/** Ordem do segmented control no design: Matriz · Filial · Lam. Matriz · Lam. Filial. */
export const ROTAS_ORDEM_UI: Rota[] = ["matriz", "filial", "lam_matriz", "lam_filial"];

/** Contrato da arte (RF-001) — validado no client E no server. */
export const ARTE_TIPOS = ["image/jpeg", "image/png"] as const;
export const ARTE_TAMANHO_MAXIMO = 10 * 1024 * 1024; // 10 MB

export type Prova = {
  id: string;
  codigo: string;
  nome: string;
  requerimento: string;
  cliente: string;
  vendedor_id: string;
  rota: Rota;
  status: string;
  created_at: string | null;
};

export type CriarProvaPayload = {
  nome: string;
  requerimento: string;
  cliente: string;
  vendedorId: string;
  rota: Rota;
  arte: File;
};

export function criarProva(payload: CriarProvaPayload): Promise<Prova> {
  const form = new FormData();
  form.set("nome", payload.nome);
  form.set("requerimento", payload.requerimento);
  form.set("cliente", payload.cliente);
  form.set("vendedor_id", payload.vendedorId);
  form.set("rota", payload.rota);
  form.set("arte", payload.arte);
  // Upload de até 10 MB: timeout maior que o padrão de 10s do client.
  return apiFetch<Prova>("/provas", { method: "POST", body: form, timeoutMs: 60_000 });
}

export function baixarEtiqueta(provaId: string): Promise<Blob> {
  return apiFetchBlob(`/provas/${provaId}/etiqueta.pdf`, { timeoutMs: 30_000 });
}

/** Dispara o download do blob no browser (etiqueta para impressão — RF-003). */
export function salvarArquivo(blob: Blob, nomeArquivo: string): void {
  const url = URL.createObjectURL(blob);
  const ancora = document.createElement("a");
  ancora.href = url;
  ancora.download = nomeArquivo;
  document.body.appendChild(ancora);
  ancora.click();
  ancora.remove();
  URL.revokeObjectURL(url);
}
