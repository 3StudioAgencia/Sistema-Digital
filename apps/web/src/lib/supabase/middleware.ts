/**
 * Refresh de sessão no middleware (@supabase/ssr) — W1-C03.
 *
 * updateSession revalida/renova o JWT a cada navegação e reemite os cookies de
 * sessão. É a ÚNICA responsabilidade do middleware nesta wave — SEM RBAC (o
 * enforcement por perfil chega no W1-C05, lendo lib/access-matrix.ts).
 *
 * Regras críticas:
 * - Use getUser() (valida no servidor de auth), nunca getSession() (§3.2).
 * - NÃO rodar código entre createServerClient e getUser().
 * - Respostas com Set-Cookie de refresh NÃO podem ser cacheadas por CDN/ISR,
 *   sob risco de servir a sessão de um usuário a outro (§3.5) → no-store.
 */
import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import { getSupabaseEnv } from "./env";

export async function updateSession(request: NextRequest): Promise<NextResponse> {
  let response = NextResponse.next({ request });
  const { url, anonKey } = getSupabaseEnv();

  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  // NÃO inserir código entre o createServerClient acima e o getUser abaixo.
  await supabase.auth.getUser();

  // §3.5: nunca cachear respostas que carregam refresh de sessão.
  response.headers.set("Cache-Control", "no-store");
  return response;
}
