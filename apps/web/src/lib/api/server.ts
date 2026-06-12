/**
 * Acesso server-side ao backend (W1-C04) — usado pelo layout do app shell.
 *
 * Busca a linha de domínio do usuário logado (GET /usuarios/me) com o access
 * token da sessão (cookies). DEGRADA para null em qualquer falha (API fora,
 * usuário não provisionado, env ausente): o shell renderiza com fallback em
 * vez de derrubar a árvore inteira (RNF-014/016).
 */
import { getSupabaseServerClient } from "@/lib/supabase/server";

import type { Usuario } from "./usuarios";

const TIMEOUT_MS = 5_000;

export async function fetchUsuarioAtual(): Promise<Usuario | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) return null;

  const supabase = await getSupabaseServerClient();
  // getSession aqui NÃO protege nada (a proteção é o getUser do layout) — só
  // fornece o access token para a chamada ao NOSSO backend.
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) return null;

  try {
    const response = await fetch(`${base}/usuarios/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return null;
    return (await response.json()) as Usuario;
  } catch {
    return null;
  }
}
