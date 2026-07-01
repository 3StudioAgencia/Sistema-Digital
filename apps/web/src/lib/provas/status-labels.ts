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

export function rotuloStatus(status: string): string {
  return STATUS_PROVA_LABELS[status as EstadoProva] ?? status;
}

export const ESTADOS_TERMINAIS: ReadonlySet<EstadoProva> = new Set<EstadoProva>([
  "recebida_clicheria",
  "cancelada",
]);

export function estaAtiva(status: EstadoProva): boolean {
  return !ESTADOS_TERMINAIS.has(status);
}
