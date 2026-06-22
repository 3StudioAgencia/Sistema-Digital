/**
 * Tipos de evento do Log de Auditoria (W6-C20) — rótulos + cor do ponto.
 *
 * Espelha 1:1 o `audit_evento_enum` do backend (CLAUDE.md §6 — valores lowercase).
 * As cores são o color-coding dos pontos do design (DP-3): cada tipo de evento tem
 * um ponto colorido na lista master-detail. Módulo de DADOS (sem JSX), reutilizável
 * pela view e pelos testes.
 */

export type EventoAuditoria =
  | "criou_prova"
  | "escaneou_qr"
  | "mudou_status"
  | "aprovou_prova"
  | "reprovou_prova"
  | "reiniciou_ciclo"
  | "cancelou_prova";

export const EVENTO_LABELS: Record<EventoAuditoria, string> = {
  criou_prova: "Criou prova",
  escaneou_qr: "Escaneou QR Code",
  mudou_status: "Mudou status",
  aprovou_prova: "Aprovou prova",
  reprovou_prova: "Reprovou prova",
  reiniciou_ciclo: "Reiniciou ciclo",
  cancelou_prova: "Cancelou prova",
};

/** Cor do ponto por tipo de evento (color-coding do design — DP-3). */
export const EVENTO_COR: Record<EventoAuditoria, string> = {
  criou_prova: "#f59e0b", // âmbar
  escaneou_qr: "#f97316", // laranja
  mudou_status: "#eab308", // amarelo
  aprovou_prova: "#1a1a1a", // preto (decisão aprovada)
  reprovou_prova: "#ef4444", // vermelho (reprovação)
  reiniciou_ciclo: "#3b82f6", // azul (construtivo)
  cancelou_prova: "#6b7280", // cinza (terminal administrativo)
};

/** Ordem do dropdown "Eventos" (criação → escaneamento → transições da §6). */
export const EVENTO_ORDEM: EventoAuditoria[] = [
  "criou_prova",
  "escaneou_qr",
  "mudou_status",
  "aprovou_prova",
  "reprovou_prova",
  "reiniciou_ciclo",
  "cancelou_prova",
];

/** Rótulo legível de um evento; cai no valor cru se vier algo fora do enum. */
export function rotuloEvento(evento: string): string {
  return EVENTO_LABELS[evento as EventoAuditoria] ?? evento;
}

/** Cor do ponto de um evento; cinza neutro para valores desconhecidos. */
export function corEvento(evento: string): string {
  return EVENTO_COR[evento as EventoAuditoria] ?? "#9ca3af";
}
