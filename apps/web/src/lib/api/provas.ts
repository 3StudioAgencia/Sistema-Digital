/**
 * Tipos e operações do recurso /provas (W2-C06).
 *
 * Espelho 1:1 dos schemas do backend (apps/api .../http/provas.py). Os VALORES
 * dos enums são os canônicos do glossário (CLAUDE.md §6 — lowercase); rótulos
 * de UI em ROTA_LABELS. A criação é multipart (arte JPG/PNG ≤ 10 MB — RF-001)
 * e a etiqueta chega como PDF binário gerado sob demanda (DP-7).
 */
import type { EstadoProva } from "@/lib/provas/status-labels";

import { apiFetch, apiFetchBlob } from "./client";
import type { Usuario } from "./usuarios";

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
  /** Chave de idempotência (RNF-015): reenvio após timeout converge no backend
   * em vez de duplicar. Gerada uma vez pela tela e reusada nas retentativas. */
  provaId?: string;
};

export function criarProva(payload: CriarProvaPayload): Promise<Prova> {
  const form = new FormData();
  form.set("nome", payload.nome);
  form.set("requerimento", payload.requerimento);
  form.set("cliente", payload.cliente);
  form.set("vendedor_id", payload.vendedorId);
  form.set("rota", payload.rota);
  form.set("arte", payload.arte);
  if (payload.provaId) form.set("prova_id", payload.provaId);
  // Upload de até 10 MB: timeout maior que o padrão de 10s do client.
  return apiFetch<Prova>("/provas", { method: "POST", body: form, timeoutMs: 60_000 });
}

export function baixarEtiqueta(provaId: string): Promise<Blob> {
  return apiFetchBlob(`/provas/${provaId}/etiqueta.pdf`, { timeoutMs: 30_000 });
}

// ---------------------------------------------------------------------------
// Listagem (W2-C07) — espelho de PaginaProvasOut/ProvaListagemOut do backend.
// ---------------------------------------------------------------------------
export type ProvaListagem = {
  id: string;
  codigo: string;
  nome: string;
  requerimento: string;
  cliente: string;
  vendedor_id: string;
  /** Resolvido pela projeção SECURITY DEFINER (DP-7); `null` no caso degenerado. */
  vendedor_nome: string | null;
  rota: Rota;
  status: EstadoProva;
  created_at: string | null;
  /** Carimbo terminal (populado pelo C11); `null` até lá. */
  finalizada_em: string | null;
};

export type PaginaProvas = {
  items: ProvaListagem[];
  total: number;
  page: number;
  page_size: number;
};

export type VendedorRef = { id: string; nome: string };

/** Filtros da barra (o "Criada em"/"Finalizada em" do design é um ÚNICO dia). */
export type FiltrosProvas = {
  busca?: string;
  cliente?: string;
  status?: EstadoProva | "";
  rota?: Rota | "";
  vendedorId?: string;
  /** Dia exato (YYYY-MM-DD) — vira limite inferior E superior no backend. */
  criada?: string;
  finalizada?: string;
  page?: number;
  pageSize?: number;
};

export function listarProvas(
  filtros: FiltrosProvas = {},
  signal?: AbortSignal,
): Promise<PaginaProvas> {
  const params = new URLSearchParams();
  if (filtros.busca) params.set("busca", filtros.busca);
  if (filtros.cliente) params.set("cliente", filtros.cliente);
  if (filtros.status) params.set("status", filtros.status);
  if (filtros.rota) params.set("rota", filtros.rota);
  if (filtros.vendedorId) params.set("vendedor_id", filtros.vendedorId);
  // Um dia escolhido cobre o dia inteiro (criada_de = criada_ate = dia).
  if (filtros.criada) {
    params.set("criada_de", filtros.criada);
    params.set("criada_ate", filtros.criada);
  }
  if (filtros.finalizada) {
    params.set("finalizada_de", filtros.finalizada);
    params.set("finalizada_ate", filtros.finalizada);
  }
  params.set("page", String(filtros.page ?? 1));
  params.set("page_size", String(filtros.pageSize ?? 20));
  return apiFetch<PaginaProvas>(`/provas?${params.toString()}`, { signal });
}

/** Vendedores em escopo (distintos das provas visíveis) — popula o dropdown. */
export function listarVendedoresProvas(signal?: AbortSignal): Promise<VendedorRef[]> {
  return apiFetch<VendedorRef[]>("/provas/vendedores", { signal });
}

/**
 * Escopo de dado por perfil (DP-2) — deriva do `usuario` corrente para ADAPTAR a
 * UI (esconder o filtro Vendedor quando o escopo é "as próprias"). É só uma dica
 * de UI: a fonte da verdade do escopo é a RLS de `provas` (C06), no servidor.
 *
 * `administrador` é ortogonal ao setor (ADR-023): um vendedor-admin vê TODAS
 * (policy admin da RLS), então o filtro Vendedor faz sentido para ele.
 */
export type EscopoProvas = "todas" | "proprias" | "em_transito";

export function escopoDeProvas(usuario: Usuario | null): EscopoProvas {
  if (!usuario) return "todas";
  if (usuario.administrador) return "todas";
  if (usuario.setor === "vendedor") return "proprias";
  if (usuario.setor === "motorista") return "em_transito";
  return "todas"; // studio, clicheria
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
