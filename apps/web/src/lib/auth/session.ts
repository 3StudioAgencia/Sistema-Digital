/**
 * Leitura da sessão no servidor (SSR / server components) — migração Supabase->local.
 *
 * Substitui o `getSupabaseServerClient().auth.getUser()`: lê o cookie httpOnly
 * `access_token` e devolve os claims verificados (ou null). Usa `next/headers`,
 * então é SÓ para o servidor (o proxy/Edge usa `verificarToken` direto).
 */
import { cookies } from "next/headers";
import type { JWTPayload } from "jose";

import { ACCESS_COOKIE, verificarToken } from "./verify";

/** Claims da sessão atual (ou null se não autenticado). */
export async function lerSessao(): Promise<JWTPayload | null> {
  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) return null;
  return verificarToken(token);
}
