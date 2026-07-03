/**
 * Tipos e operações do recurso /provas (W2-C06).
 *
 * Espelho 1:1 dos schemas do backend (apps/api .../http/provas.py). Os VALORES
 * dos enums são os canônicos do glossário (CLAUDE.md §6 — lowercase); rótulos
 * de UI em ROTA_LABELS. A criação nasce do NÚMERO DE REQUERIMENTO (Fatia 4): o
 * servidor resolve nome/cliente/vendedor no ERP (Firebird) e a imagem no servidor
 * de arquivos; a etiqueta chega como PDF binário gerado sob demanda (RF-003).
 */
import type { EstadoProva } from "@/lib/provas/status-labels";

import { apiFetch, apiFetchBlob } from "./client";
import type { Usuario } from "./usuarios";

// Rótulos de rota vivem em módulo próprio (DP-7), espelhando os de status; aqui
// re-exportados para os imports já existentes (C06/C07) seguirem funcionando.
export type { Rota } from "@/lib/provas/rota-labels";
export { ROTA_LABELS, ROTAS_ORDEM_UI, rotuloRota } from "@/lib/provas/rota-labels";

import type { Rota } from "@/lib/provas/rota-labels";

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

/** Dados do requerimento resolvidos no ERP (Firebird) — preview da criação (Fatia 4). */
export type RequerimentoResolvido = {
  cod_req_art: number;
  nome: string | null;
  cod_cliente: number;
  nome_cliente: string | null;
  cod_vendedor: number;
  nome_vendedor: string | null;
  cod_vend_fat: number | null;
  anexo_imagem: string | null;
};

/** Consulta o requerimento no ERP (admin-only): 404 se inexistente, 503 se ERP fora. */
export function consultarRequerimento(
  codReqArt: number,
  signal?: AbortSignal,
): Promise<RequerimentoResolvido> {
  return apiFetch<RequerimentoResolvido>(`/provas/requerimento/${codReqArt}`, { signal });
}

/** Imagem oficial do requerimento (proxy do share, sem criar a prova) — preview da
 * criação. Blob → objectURL num <img>, como o proxy da arte no detalhe (DP-5). */
export function baixarArteRequerimento(codReqArt: number, signal?: AbortSignal): Promise<Blob> {
  return apiFetchBlob(`/provas/requerimento/${codReqArt}/arte`, { signal, timeoutMs: 30_000 });
}

export type CriarProvaPayload = {
  codReqArt: number;
  rota: Rota;
  /** Chave de idempotência (RNF-015): reenvio após timeout converge no backend
   * em vez de duplicar. Gerada uma vez pela tela e reusada nas retentativas. */
  provaId?: string;
};

/** Criação por REQUERIMENTO (Fatia 4): o backend resolve nome/cliente/vendedor no
 * ERP e a imagem no servidor de arquivos. Só o número e a rota vêm do cliente. */
export function criarProva(payload: CriarProvaPayload): Promise<Prova> {
  return apiFetch<Prova>("/provas", {
    method: "POST",
    body: {
      cod_req_art: payload.codReqArt,
      rota: payload.rota,
      ...(payload.provaId ? { prova_id: payload.provaId } : {}),
    },
    // Resolução ERP + leitura no share podem passar dos 10s padrão do client.
    timeoutMs: 60_000,
  });
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
  /** Um valor = filtro simples; vários = "qualquer um" (IN) — deep-link do
   * Dashboard (ex.: "Com Vendedor" = retirada + encaminhada — W4-C16/DP-6). */
  status?: EstadoProva | EstadoProva[] | "";
  rota?: Rota | "";
  vendedorId?: string;
  /** Dia exato (YYYY-MM-DD) — vira limite inferior E superior no backend. */
  criada?: string;
  finalizada?: string;
  /** Filtro "Atrasadas" (W4-C16/DP-6): reusa a regra de horas úteis do backend. */
  atrasada?: boolean;
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
  // status pode ser múltiplo (?status=a&status=b) ou simples — o backend trata
  // ambos (lista vazia = sem filtro).
  if (Array.isArray(filtros.status)) {
    for (const s of filtros.status) if (s) params.append("status", s);
  } else if (filtros.status) {
    params.set("status", filtros.status);
  }
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
  if (filtros.atrasada) params.set("atrasada", "true");
  params.set("page", String(filtros.page ?? 1));
  params.set("page_size", String(filtros.pageSize ?? 20));
  return apiFetch<PaginaProvas>(`/provas?${params.toString()}`, { signal });
}

/** Vendedores em escopo (distintos das provas visíveis) — popula o dropdown. */
export function listarVendedoresProvas(signal?: AbortSignal): Promise<VendedorRef[]> {
  return apiFetch<VendedorRef[]>("/provas/vendedores", { signal });
}

// ---------------------------------------------------------------------------
// Detalhe (W2-C08) — espelho de ProvaDetalheOut do backend (GET /provas/{id}).
// ---------------------------------------------------------------------------
export type ProvaDetalhe = {
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
  /** Ciclo de revisão (DP-1): nasce 1, incrementado pelo C15. */
  ciclo_atual: number;
  created_at: string | null;
  /** Carimbo terminal (populado pelo C11); `null` até lá. */
  finalizada_em: string | null;
};

/** Detalhe de uma prova; 404 (ApiError.status) = inexistente OU fora do escopo
 * (mesmo caso — anti-enumeração). O ESCOPO de dado é da RLS, no servidor. */
export function obterProva(id: string, signal?: AbortSignal): Promise<ProvaDetalhe> {
  return apiFetch<ProvaDetalhe>(`/provas/${id}`, { signal });
}

/** Arte da prova como blob, via PROXY do backend (DP-5): a key do R2 nunca é
 * exposta e não há URL pública. Para exibir: `URL.createObjectURL(blob)`. */
export function baixarArte(id: string, signal?: AbortSignal): Promise<Blob> {
  return apiFetchBlob(`/provas/${id}/arte`, { signal, timeoutMs: 30_000 });
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
