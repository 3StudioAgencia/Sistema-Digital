/**
 * Código identificador da prova (C06/C10) — espelho do domínio do backend
 * (apps/api/src/domain/provas.py). Fonte ÚNICA no front para a máscara/validação
 * do input manual e o parsing do payload do QR.
 *
 * Formato canônico (DP-1): `PRV-AAAA-MM-NNNNNN`. O QR carrega o PRÓPRIO código
 * (sem URL — C06), então leitura por câmera e digitação manual batem no MESMO
 * valor. A validação AUTORITATIVA é do servidor (anti-enumeração — RN-014); aqui
 * é só UX (habilitar o botão, mascarar a digitação). Por isso a mensagem do
 * design ("3S- / 8 dígitos") é legado: o que vale é o que o C06 imprime.
 */

/** Charset não ambíguo do sufixo (sem `0/O`, `1/I/L`) — 31 símbolos (= backend). */
export const CODIGO_ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";
export const CODIGO_PREFIXO = "PRV";

/** Espelho de `CODIGO_REGEX` (domain/provas.py): `PRV-AAAA-MM-<6 do alfabeto>`. */
export const CODIGO_REGEX = /^PRV-\d{4}-(0[1-9]|1[0-2])-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{6}$/;

/** Normaliza como o servidor: trim + MAIÚSCULAS (idempotente para o QR). */
export function normalizarCodigo(bruto: string): string {
  return bruto.trim().toUpperCase();
}

/** `true` se o texto já está na forma canônica (habilita "Buscar prova"). */
export function validarCodigo(codigo: string): boolean {
  return CODIGO_REGEX.test(normalizarCodigo(codigo));
}

/**
 * Máscara da parte EDITÁVEL do código (depois do prefixo fixo `PRV-`): agrupa a
 * digitação em `AAAA-MM-XXXXXX`, inserindo os hífens automaticamente. Tolera a
 * colagem do código inteiro (remove um `PRV-` inicial) e descarta caracteres
 * inválidos. Não força dígito-vs-letra por posição — quem decide a validade é
 * `validarCodigo` (que habilita o botão); a máscara só dá forma.
 */
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

/** Recompõe o código completo a partir da parte editável (com o prefixo fixo). */
export function montarCodigo(resto: string): string {
  return `${CODIGO_PREFIXO}-${resto}`;
}
