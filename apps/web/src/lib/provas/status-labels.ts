/**
 * Rótulos de UI dos 14 estados da prova (W2-C07 / DP-4) — módulo REUTILIZÁVEL
 * (C08 detalhe, C13 timeline, C16 dashboard reusam).
 *
 * Os VALORES são os canônicos do `status_prova_enum` (CLAUDE.md §6 — lowercase),
 * sincronizados 1:1 com `EstadoProva` do backend. Os RÓTULOS são curtos por
 * estado (decisão DP-4 do dono), adotando a grafia do design onde há amostra
 * ("Aprovada", "Reprovada", "Na 3Studio", "Na clicheria", "Retirada", "Cancelada")
 * e formas concisas para os demais. O filtro de Status lista os 14 + "Todos".
 */

export type EstadoProva =
  | "criada"
  | "encaminhada_para_laminacao"
  | "com_motorista_ida_laminacao"
  | "laminacao_concluida"
  | "com_motorista_volta_laminacao"
  | "de_volta_studio_pos_laminacao"
  | "retirada_vendedor"
  | "encaminhada_para_vendedor"
  | "aprovada_vendedor"
  | "reprovada_vendedor"
  | "de_volta_studio"
  | "com_motorista_entrega_final"
  | "recebida_clicheria"
  | "cancelada";

export const STATUS_PROVA_LABELS: Record<EstadoProva, string> = {
  criada: "Criada",
  encaminhada_para_laminacao: "Encaminhada p/ laminação",
  com_motorista_ida_laminacao: "Com motorista — ida laminação",
  laminacao_concluida: "Laminação concluída",
  com_motorista_volta_laminacao: "Com motorista — volta laminação",
  de_volta_studio_pos_laminacao: "Na 3Studio (pós-laminação)",
  retirada_vendedor: "Retirada",
  encaminhada_para_vendedor: "Encaminhada ao vendedor",
  aprovada_vendedor: "Aprovada",
  reprovada_vendedor: "Reprovada",
  de_volta_studio: "Na 3Studio",
  com_motorista_entrega_final: "Com motorista — entrega final",
  recebida_clicheria: "Na clicheria",
  cancelada: "Cancelada",
};

/** Ordem canônica do fluxo (glossário §6) — usada no dropdown de Status. */
export const STATUS_PROVA_ORDEM: EstadoProva[] = [
  "criada",
  "encaminhada_para_laminacao",
  "com_motorista_ida_laminacao",
  "laminacao_concluida",
  "com_motorista_volta_laminacao",
  "de_volta_studio_pos_laminacao",
  "retirada_vendedor",
  "encaminhada_para_vendedor",
  "aprovada_vendedor",
  "reprovada_vendedor",
  "de_volta_studio",
  "com_motorista_entrega_final",
  "recebida_clicheria",
  "cancelada",
];

/** Rótulo legível de um status; cai no valor cru se vier algo fora do enum. */
export function rotuloStatus(status: string): string {
  return STATUS_PROVA_LABELS[status as EstadoProva] ?? status;
}

/**
 * Estados TERMINAIS (≠ ativo) — espelham `ESTADOS_TERMINAIS` do backend (§6):
 * uma prova nesses estados não tem transição de saída. Usado pelo C14 para só
 * oferecer "Cancelar" em estados ATIVOS (a fonte da verdade é o motor — aqui é a
 * mesma regra estável dos 2 terminais, como os 14 rótulos espelham o enum).
 */
export const ESTADOS_TERMINAIS: ReadonlySet<EstadoProva> = new Set<EstadoProva>([
  "recebida_clicheria",
  "cancelada",
]);

/** Uma prova ATIVA (≠ terminal) pode ser cancelada (W3-C14 — RF-011/§6.6). */
export function estaAtiva(status: EstadoProva): boolean {
  return !ESTADOS_TERMINAIS.has(status);
}
