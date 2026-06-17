/**
 * Formatação dos números dos Relatórios (W5-C17) — pt-BR.
 *
 * Métricas sem base (média sem aprovações, taxa sem decisões) chegam `null` do
 * backend e viram "—" (em vez de 0 enganoso — DP-3). Tempo em HORAS (unidade do
 * design — DP-3). Módulo puro, reutilizável e testável.
 */

/** Inteiro pt-BR (separador de milhar). */
export function fmtInt(valor: number): string {
  return new Intl.NumberFormat("pt-BR").format(Math.round(valor));
}

/** Decimal com 1 casa (vírgula) ou "—" quando ausente. */
export function fmtDec(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

/** Horas úteis: "12,5 h" ou "—". */
export function fmtHoras(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return `${fmtDec(valor)} h`;
}

/** Percentual: "8,0%" ou "—". */
export function fmtPct(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return `${fmtDec(valor)}%`;
}

/** Iniciais para o avatar (1ª letra do 1º e último nome). */
export function iniciais(nome: string | null): string {
  if (!nome) return "—";
  const partes = nome.trim().split(/\s+/);
  const primeira = partes[0]?.[0] ?? "";
  const ultima = partes.length > 1 ? (partes[partes.length - 1][0] ?? "") : "";
  return (primeira + ultima).toUpperCase() || "—";
}

/** Fração [0,1] de um valor sobre o máximo (largura de barra), segura a divisão. */
export function fracao(valor: number, maximo: number): number {
  if (maximo <= 0) return 0;
  return Math.max(0, Math.min(1, valor / maximo));
}
