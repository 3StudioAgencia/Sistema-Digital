/**
 * Validações de formulário compartilhadas (W1-C04).
 *
 * Espelham as regras do backend (fonte única: apps/api src/domain/usuarios.py)
 * para feedback em tempo real — o backend revalida SEMPRE (defesa em
 * profundidade); o front nunca é a única barreira.
 */

export const SENHA_TAMANHO_MINIMO = 8;

/** Política RF-018: mínimo 8 caracteres, com pelo menos uma letra e um número. */
export function senhaValida(senha: string): boolean {
  return senha.length >= SENHA_TAMANHO_MINIMO && /[a-zA-Z]/.test(senha) && /[0-9]/.test(senha);
}

/** Forma básica de e-mail — o backend valida com email-validator (EmailStr). */
export function emailValido(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}
