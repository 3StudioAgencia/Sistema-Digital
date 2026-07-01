export const SENHA_TAMANHO_MINIMO = 8;

export function senhaValida(senha: string): boolean {
  return senha.length >= SENHA_TAMANHO_MINIMO && /[a-zA-Z]/.test(senha) && /[0-9]/.test(senha);
}

export function emailValido(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}
