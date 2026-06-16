/**
 * Tipos e fetch do histórico de movimentações (W3-C13) — espelho 1:1 do
 * `TimelineOut`/`MovimentacaoOut` do backend (apps/api .../http/provas.py).
 *
 * `etapas_canonicas` é a sequência de estados do caminho NORMAL da rota, DERIVADA
 * das `transition_rules` do C11 no backend (DP-1 — a §6 não é duplicada no front):
 * a Timeline a usa como esqueleto e sobrepõe `movimentacoes` (já em ordem
 * cronológica). `tem_assinatura` é só o SELO (DP-2c — a imagem nunca trafega).
 */
import type { Rota } from "@/lib/provas/rota-labels";
import type { EstadoProva } from "@/lib/provas/status-labels";

import { apiFetch } from "./client";

/** Ações de transição (↔ `acao_enum`/`Acao` do backend). */
export type AcaoMovimentacao =
  | "identificar_e_assinar"
  | "aprovar"
  | "reprovar"
  | "reiniciar_ciclo"
  | "cancelar";

export type Movimentacao = {
  id: string;
  estado_origem: EstadoProva;
  estado_destino: EstadoProva;
  acao: AcaoMovimentacao;
  ator_id: string;
  /** Responsável resolvido (DP-2b); `null` no caso degenerado. */
  ator_nome: string | null;
  ciclo: number;
  motivo: string | null;
  /** SELO de assinatura (DP-2c): houve comprovante desenhado — sem a imagem. */
  tem_assinatura: boolean;
  created_at: string | null;
};

export type Timeline = {
  rota: Rota;
  estado_atual: EstadoProva;
  ciclo_atual: number;
  /** Carimba o nó inicial `criada` (a prova nasce nesse estado). */
  criada_em: string | null;
  /** Esqueleto da rota (DP-1) — sequência canônica derivada das regras do C11. */
  etapas_canonicas: EstadoProva[];
  /** Histórico em ordem cronológica (asc). */
  movimentacoes: Movimentacao[];
};

/** Histórico + esqueleto da rota; o ESCOPO de dado é da RLS, no servidor.
 * 404 (ApiError.status) = inexistente OU fora do escopo (anti-enumeração). */
export function obterMovimentacoes(id: string, signal?: AbortSignal): Promise<Timeline> {
  return apiFetch<Timeline>(`/provas/${id}/movimentacoes`, { signal });
}
