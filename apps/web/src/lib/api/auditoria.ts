/**
 * Tipos e operações do recurso /auditoria (W6-C20) — log imutável (read-only).
 *
 * Espelho 1:1 dos schemas do backend (apps/api .../http/auditoria.py). 3Studio-only
 * (o proxy gateia a rota e a sidebar esconde o item; o endpoint responde 403 ao
 * não-admin). READ-ONLY: só leituras + a verificação de integridade (que NÃO altera
 * o log — apenas recomputa o chain).
 */
import type { EstadoProva } from "@/lib/provas/status-labels";
import type { EventoAuditoria } from "@/lib/auditoria/evento-labels";

import { apiFetch } from "./client";

export type AcaoAuditoria =
  | "identificar_e_assinar"
  | "aprovar"
  | "reprovar"
  | "reiniciar_ciclo"
  | "cancelar";

export type RegistroAuditoria = {
  id: string;
  seq: number;
  evento: EventoAuditoria;
  ator_id: string;
  /** Resolvido por JOIN a usuarios (admin vê todos); `null` no caso degenerado. */
  ator_nome: string | null;
  ator_setor: string | null;
  prova_id: string | null;
  prova_codigo: string | null;
  prova_cliente: string | null;
  prova_requerimento: string | null;
  acao: AcaoAuditoria | null;
  estado_origem: EstadoProva | null;
  estado_destino: EstadoProva | null;
  ciclo: number | null;
  motivo: string | null;
  ip: string | null;
  /** Rótulo de origem já formatado ("Aplicação Web · Chrome"); `null` sem UA. */
  origem: string | null;
  created_at: string;
  /** Elo do chain de integridade (hex sha256). */
  hash: string;
};

export type PaginaAuditoria = {
  items: RegistroAuditoria[];
  total: number;
  page: number;
  page_size: number;
};

export type AtorAuditoria = { id: string; nome: string | null };

export type IntegridadeAuditoria = {
  intacto: boolean;
  total: number;
  /** `seq` da 1ª linha divergente; `null` quando o chain está íntegro. */
  quebrou_em: number | null;
};

export type OrdemAuditoria = "recentes" | "antigos";

export type FiltrosAuditoria = {
  evento?: EventoAuditoria | "";
  atorId?: string;
  busca?: string;
  /** Dia exato (YYYY-MM-DD). */
  de?: string;
  ate?: string;
  ordem?: OrdemAuditoria;
  page?: number;
  pageSize?: number;
};

export function listarAuditoria(
  filtros: FiltrosAuditoria = {},
  signal?: AbortSignal,
): Promise<PaginaAuditoria> {
  const params = new URLSearchParams();
  if (filtros.evento) params.set("evento", filtros.evento);
  if (filtros.atorId) params.set("ator_id", filtros.atorId);
  if (filtros.busca) params.set("busca", filtros.busca);
  if (filtros.de) params.set("de", filtros.de);
  if (filtros.ate) params.set("ate", filtros.ate);
  if (filtros.ordem) params.set("ordem", filtros.ordem);
  params.set("page", String(filtros.page ?? 1));
  params.set("page_size", String(filtros.pageSize ?? 50));
  return apiFetch<PaginaAuditoria>(`/auditoria?${params.toString()}`, { signal });
}

/** Atores distintos do log (popula o dropdown "Ator"). */
export function listarAtoresAuditoria(signal?: AbortSignal): Promise<AtorAuditoria[]> {
  return apiFetch<AtorAuditoria[]>("/auditoria/atores", { signal });
}

/** Recomputa o chain do log e devolve o veredito de integridade (tamper-evidence).
 * É read-only no log: a verificação apenas recalcula e compara (não muta nada). */
export function verificarIntegridadeAuditoria(
  signal?: AbortSignal,
): Promise<IntegridadeAuditoria> {
  return apiFetch<IntegridadeAuditoria>("/auditoria/verificar-integridade", {
    method: "POST",
    signal,
  });
}
