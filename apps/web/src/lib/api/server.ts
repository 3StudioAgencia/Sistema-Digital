/**
 * Acesso server-side ao backend (migração Supabase->local).
 *
 * Lê o cookie httpOnly `access_token` (via next/headers) e chama o backend
 * DIRETO por `BACKEND_INTERNAL_URL` (SSR não usa o rewrite /api, que é do
 * browser), com Bearer. DEGRADA para null em qualquer falha (API fora, sessão
 * ausente, env): o shell renderiza com fallback em vez de derrubar a árvore
 * (RNF-014/016).
 */
import { cookies } from "next/headers";
import { cache } from "react";

import { ACCESS_COOKIE } from "@/lib/auth/verify";

import type { Dashboard } from "./dashboard";
import type { Usuario } from "./usuarios";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
// Curto de propósito: este fetch roda NO SERVIDOR antes do primeiro byte do
// shell — com a API fora, o TTFB ficaria preso aqui. 2s cobre o caso normal.
const TIMEOUT_MS = 2_000;

async function backendGet<T>(path: string): Promise<T | null> {
  const token = (await cookies()).get(ACCESS_COOKIE)?.value;
  if (!token) return null;
  try {
    const response = await fetch(`${BACKEND}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

// Memoizado por REQUISIÇÃO (React `cache`): o layout e uma página que também
// precise do perfil compartilham UMA ida ao /usuarios/me por render (RNF-020).
export const fetchUsuarioAtual = cache(
  async (): Promise<Usuario | null> => backendGet<Usuario>("/usuarios/me"),
);

// Carga INICIAL do dashboard no servidor (W4-C16): evita waterfall no cliente.
export async function fetchDashboard(): Promise<Dashboard | null> {
  return backendGet<Dashboard>("/dashboard");
}
