/**
 * Tipos e operações do recurso /relatorios (W5-C17).
 *
 * Espelho 1:1 dos schemas do backend (apps/api .../http/relatorios.py). Exclusivo
 * do 3Studio (flag admin — a página é gateada pelo proxy; os endpoints respondem
 * 403 ao não-admin). Uma agregação por ABA, buscada SÓ quando a aba está ativa
 * (lazy — DP-6); SEM Realtime (snapshot do período — recomputa na troca de
 * filtro/aba). Os tempos vêm em HORAS ÚTEIS (mesma base do C16).
 */
import type { Rota } from "@/lib/provas/rota-labels";
import type { EstadoProva } from "@/lib/provas/status-labels";

import { apiFetch, apiFetchBlob } from "./client";

export type { Rota } from "@/lib/provas/rota-labels";
export type { EstadoProva } from "@/lib/provas/status-labels";

export type Aba = "geral" | "studio" | "vendedores" | "clicheria";

export type FatiaRota = { rota: Rota; total: number };
export type PontoVolume = { dia: string; total: number };

export type MetricaVendedor = {
  vendedor_id: string;
  vendedor_nome: string | null;
  localizacao: string | null;
  volume: number;
  aprovadas: number;
  reprovadas: number;
  /** `null` quando não houve decisão (sem aprov/reprov) — a UI mostra "—". */
  taxa_reprovacao: number | null;
  tempo_medio_horas: number | null;
  atrasadas: number;
};

export type ProvaAtrasada = {
  id: string;
  nome: string;
  requerimento: string;
  cliente: string;
  vendedor_id: string;
  vendedor_nome: string | null;
  status: EstadoProva;
  atraso_horas: number;
};

export type MotivoCancelamento = { motivo: string; total: number };

export type RelatorioGeral = {
  total_geral: number;
  volume: PontoVolume[];
  tempo_medio_aprovacao_horas: number | null;
  taxa_reprovacao: number | null;
  distribuicao_rota: FatiaRota[];
  ativas_aguardando_vendedor: number;
  ativas_reprovadas: number;
  metricas_por_vendedor: MetricaVendedor[];
  provas_atrasadas: ProvaAtrasada[];
};

export type RelatorioStudio = {
  provas_criadas: number;
  media_diaria: number;
  reinicios_ciclo: number;
  devolvidas: number;
  cancelamentos: number;
  reprovadas_aguardando: number;
  tempo_ate_primeira_mov_horas: number | null;
  top_motivos_cancelamento: MotivoCancelamento[];
};

export type RelatorioVendedores = {
  vendedores_filial: number;
  vendedores_matriz: number;
  vendedores_ativos: number;
  atrasadas_total: number;
  por_vendedor: MetricaVendedor[];
};

export type RelatorioClicheria = {
  tempo_medio_aguardando_horas: number | null;
  recebidas_no_periodo: number;
  em_transito_agora: number;
  origens: number;
  distribuicao_origem: FatiaRota[];
};

/** Toggle de rota do design (2 vias) — agrupa as 4 rotas do domínio (DP-4). */
export type GrupoRota = "" | "matriz" | "filial";

/** Estado da barra de filtros compartilhada (DP-4). `grupoRota` é o toggle 2-vias. */
export type FiltrosRelatorio = {
  de?: string;
  ate?: string;
  status?: EstadoProva | "";
  grupoRota?: GrupoRota;
  busca?: string;
  vendedorId?: string;
};

/** Expande o toggle 2-vias para as rotas reais do domínio (DP-4). */
export function rotasDoGrupo(grupo: GrupoRota | undefined): Rota[] {
  if (grupo === "matriz") return ["matriz", "lam_matriz"];
  if (grupo === "filial") return ["filial", "lam_filial"];
  return [];
}

function queryDeFiltros(filtros: FiltrosRelatorio): URLSearchParams {
  const params = new URLSearchParams();
  if (filtros.de) params.set("de", filtros.de);
  if (filtros.ate) params.set("ate", filtros.ate);
  if (filtros.status) params.set("status", filtros.status);
  for (const r of rotasDoGrupo(filtros.grupoRota)) params.append("rota", r);
  if (filtros.busca) params.set("busca", filtros.busca);
  if (filtros.vendedorId) params.set("vendedor_id", filtros.vendedorId);
  return params;
}

function buscar<T>(aba: Aba, filtros: FiltrosRelatorio, signal?: AbortSignal): Promise<T> {
  const qs = queryDeFiltros(filtros).toString();
  return apiFetch<T>(`/relatorios/${aba}${qs ? `?${qs}` : ""}`, { signal });
}

export const fetchRelatorioGeral = (f: FiltrosRelatorio, s?: AbortSignal) =>
  buscar<RelatorioGeral>("geral", f, s);
export const fetchRelatorioStudio = (f: FiltrosRelatorio, s?: AbortSignal) =>
  buscar<RelatorioStudio>("studio", f, s);
export const fetchRelatorioVendedores = (f: FiltrosRelatorio, s?: AbortSignal) =>
  buscar<RelatorioVendedores>("vendedores", f, s);
export const fetchRelatorioClicheria = (f: FiltrosRelatorio, s?: AbortSignal) =>
  buscar<RelatorioClicheria>("clicheria", f, s);

/** Baixa o CSV da aba (DP-5), respeitando os filtros ativos. Dispara o download. */
export async function exportarRelatorioCsv(aba: Aba, filtros: FiltrosRelatorio): Promise<void> {
  const params = queryDeFiltros(filtros);
  params.set("aba", aba);
  const blob = await apiFetchBlob(`/relatorios/exportar?${params.toString()}`, {
    timeoutMs: 30_000,
  });
  const url = URL.createObjectURL(blob);
  const ancora = document.createElement("a");
  ancora.href = url;
  ancora.download = `relatorio-${aba}.csv`;
  document.body.appendChild(ancora);
  ancora.click();
  ancora.remove();
  URL.revokeObjectURL(url);
}

/** Vendedores em escopo para o dropdown de filtro (reusa o endpoint do C07). */
export { listarVendedoresProvas as listarVendedores } from "./provas";
