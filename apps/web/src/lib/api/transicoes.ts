/**
 * Transição da máquina de estados + assinatura do fluxo (W3-C11/C12).
 *
 * `acoesDisponiveis` (GET) orienta a tela de confirmação: o backend reusa as
 * regras do C11 e devolve só as ações do fluxo de escaneamento que ESTE ator pode
 * executar agora (lista vazia = não é a vez dele → bloqueio genérico, sem revelar
 * quem é — RN-014). `executarTransicao` (POST) envia a assinatura DESENHADA (PNG
 * base64) + a ação; o backend grava assinatura+movimentação atomicamente
 * (nascem/falham juntas — RNF-017). `idempotencyKey` reusado nas retentativas
 * converge (RNF-015), sem duplicar — base da resiliência (DP-5).
 */
import type { EstadoProva } from "@/lib/provas/status-labels";

import { apiFetch } from "./client";
import type { ProvaDetalhe } from "./provas";

export type Acao =
  | "identificar_e_assinar"
  | "aprovar"
  | "reprovar"
  | "reiniciar_ciclo"
  | "cancelar";

/** Espelho de `AcaoDisponivelOut` do backend. */
export type AcaoDisponivel = {
  acao: Acao;
  exige_motivo: boolean;
  estado_destino: EstadoProva;
};

export function acoesDisponiveis(provaId: string, signal?: AbortSignal): Promise<AcaoDisponivel[]> {
  return apiFetch<AcaoDisponivel[]>(`/provas/${provaId}/acoes-disponiveis`, { signal });
}

export type TransicaoPayload = {
  acao: Acao;
  /** PNG da assinatura desenhada (data-URL `data:image/png;base64,...` ou base64 puro). */
  assinatura: string;
  /** Chave de idempotência (RNF-015): reusada nas retentativas → converge. */
  idempotencyKey: string;
  /** Obrigatório só para Reprovar (validado no backend). */
  motivo?: string;
};

export function executarTransicao(
  provaId: string,
  payload: TransicaoPayload,
): Promise<ProvaDetalhe> {
  return apiFetch<ProvaDetalhe>(`/provas/${provaId}/transicoes`, {
    method: "POST",
    body: {
      acao: payload.acao,
      assinatura: payload.assinatura,
      idempotency_key: payload.idempotencyKey,
      ...(payload.motivo !== undefined ? { motivo: payload.motivo } : {}),
    },
    // Imagem base64 + transação atômica: mais folga que o GET padrão (10s).
    timeoutMs: 30_000,
  });
}
