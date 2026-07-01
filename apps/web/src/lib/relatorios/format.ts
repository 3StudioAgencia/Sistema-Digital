export function fmtInt(valor: number): string {
  return new Intl.NumberFormat("pt-BR").format(Math.round(valor));
}

export function fmtDec(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export function fmtHoras(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return `${fmtDec(valor)} h`;
}

export function fmtPct(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return `${fmtDec(valor)}%`;
}

export function iniciais(nome: string | null): string {
  if (!nome) return "—";
  const partes = nome.trim().split(/\s+/);
  const primeira = partes[0]?.[0] ?? "";
  const ultima = partes.length > 1 ? (partes[partes.length - 1][0] ?? "") : "";
  return (primeira + ultima).toUpperCase() || "—";
}

export function fracao(valor: number, maximo: number): number {
  if (maximo <= 0) return 0;
  return Math.max(0, Math.min(1, valor / maximo));
}
