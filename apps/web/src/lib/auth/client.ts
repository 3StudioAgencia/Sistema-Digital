/**
 * Cliente de autenticação no browser (migração Supabase->local).
 *
 * Substitui `supabase.auth.signInWithPassword`/`signOut`. Chama o backend pela
 * MESMA ORIGEM (`/api/*`, rewrite do next.config.ts): o backend seta/limpa os
 * cookies httpOnly de sessão; o browser não manuseia o token.
 */

export type SessaoUsuario = {
  id: string;
  email: string;
  setor: string;
  administrador: boolean;
};

export class CredenciaisInvalidasError extends Error {}

async function postJson(path: string, body?: unknown): Promise<Response> {
  return fetch(path, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
}

/** Autentica (POST /api/auth/login). Lança em credenciais inválidas (401). */
export async function login(email: string, senha: string): Promise<SessaoUsuario> {
  const resp = await postJson("/api/auth/login", { email: email.trim(), senha });
  if (resp.status === 401) throw new CredenciaisInvalidasError();
  if (!resp.ok) throw new Error(`login falhou (${resp.status})`);
  return (await resp.json()) as SessaoUsuario;
}

/** Encerra a sessão (POST /api/auth/logout). Best-effort — os cookies são limpos no backend. */
export async function logout(): Promise<void> {
  try {
    await postJson("/api/auth/logout");
  } catch {
    // Segue para /login de qualquer forma; o access token stale expira no TTL.
  }
}
