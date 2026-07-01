export const CODIGO_ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";
export const CODIGO_PREFIXO = "PRV";
export const CODIGO_REGEX = /^PRV-\d{4}-(0[1-9]|1[0-2])-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{6}$/;
export function normalizarCodigo(bruto: string): string {
  return bruto.trim().toUpperCase();
}

export function validarCodigo(codigo: string): boolean {
  return CODIGO_REGEX.test(normalizarCodigo(codigo));
}

export function mascararResto(bruto: string): string {
  const limpo = bruto
    .toUpperCase()
    .replace(/^PRV-?/, "") // colou o código inteiro → tira o prefixo fixo
    .replace(/[^0-9A-Z]/g, "") // hífens e símbolos somem; a máscara os recoloca
    .slice(0, 12); // 4 (ano) + 2 (mês) + 6 (sufixo)
  const ano = limpo.slice(0, 4);
  const mes = limpo.slice(4, 6);
  const sufixo = limpo.slice(6, 12);
  let saida = ano;
  if (limpo.length > 4) saida += `-${mes}`;
  if (limpo.length > 6) saida += `-${sufixo}`;
  return saida;
}

export function montarCodigo(resto: string): string {
  return `${CODIGO_PREFIXO}-${resto}`;
}

export function mascararCodigo(bruto: string): string {
  const limpo = bruto
    .toUpperCase()
    .replace(/[^0-9A-Z]/g, "")
    .slice(0, 15); // PRV(3) + AAAA(4) + MM(2) + sufixo(6)
  if (limpo.length === 0) return "";
  let saida = limpo.slice(0, 3); // PRV
  if (limpo.length > 3) saida += `-${limpo.slice(3, 7)}`;
  if (limpo.length > 7) saida += `-${limpo.slice(7, 9)}`;
  if (limpo.length > 9) saida += `-${limpo.slice(9, 15)}`;
  return saida;
}
