/**
 * Identificação de prova (W3-C10) — espelho de `POST /provas/identificar`.
 *
 * QR e código manual passam pelo MESMO caminho e resolvem o MESMO registro: o
 * backend normaliza, valida o formato e escopa pela RLS. Erros (via `ApiError`):
 * - 404 (`prova_nao_encontrada`): código inválido OU inexistente OU fora do
 *   escopo — MESMA mensagem (anti-enumeração, RN-014): a UI não distingue;
 * - 429 (`limite_de_tentativas`): excesso de tentativas (30/min).
 *
 * Devolve o detalhe (`ProvaDetalhe`) já resolvido — o C10 leva à tela de
 * confirmação; validar a transição é do C11 e assinar é do C12 (DP-2).
 */
import { apiFetch } from "./client";
import type { ProvaDetalhe } from "./provas";

export function identificarProva(codigo: string, signal?: AbortSignal): Promise<ProvaDetalhe> {
  return apiFetch<ProvaDetalhe>("/provas/identificar", {
    method: "POST",
    body: { codigo },
    signal,
  });
}
