/**
 * Refresh de sessão + enforcement de RBAC no proxy do App Router.
 *
 * - W1-C03: `updateSession` revalida/renova o JWT a cada navegação e reemite os
 *   cookies de sessão (getUser() — valida no servidor de auth, nunca getSession).
 * - W1-C05: APÓS o refresh, a camada SUPERIOR do RBAC (CLAUDE.md §5.4) decide o
 *   acesso por perfil contra `lib/access-matrix.ts`. Os claims de perfil vêm de
 *   `getClaims()` (verificação LOCAL com a chave assimétrica — não bate no
 *   servidor de auth por request; pilar de mínimo de requisições). Acesso negado
 *   → 302 para a home do perfil + cookie efêmero que o toast lê no destino (DP-4).
 *
 * Regras críticas:
 * - NÃO rodar código entre createServerClient e getUser().
 * - Respostas com Set-Cookie de refresh NÃO podem ser cacheadas por CDN/ISR,
 *   sob risco de servir a sessão de um usuário a outro (§3.5) → no-store.
 * - O redirect PRESERVA os cookies de refresh (senão a sessão recém-renovada se
 *   perderia na navegação).
 */
import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import {
  FLASH_ACESSO_NEGADO,
  HOME_PADRAO,
  perfilDeClaims,
  podeAcessarRota,
} from "@/lib/access-matrix";

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
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // §3.5: nunca cachear respostas que carregam refresh de sessão.
  response.headers.set("Cache-Control", "no-store");

  // Camada superior do RBAC (W1-C05): só para usuários autenticados. A proteção
  // de autenticação (redirect p/ /login de quem não tem sessão) é do layout do
  // grupo (app) — aqui cuidamos do enforcement por PERFIL.
  if (user) {
    const { data: claims } = await supabase.auth.getClaims();
    const perfil = perfilDeClaims(claims?.claims);
    if (!podeAcessarRota(perfil, request.nextUrl.pathname)) {
      return redirectAcessoNegado(request, response);
    }
  }

  return response;
}

/**
 * Redireciona à home do perfil preservando os cookies de refresh e deixando o
 * flash de acesso negado (lido e limpo pelo toast no destino — DP-4).
 */
function redirectAcessoNegado(request: NextRequest, refreshed: NextResponse): NextResponse {
  const destino = request.nextUrl.clone();
  destino.pathname = HOME_PADRAO;
  destino.search = "";
  const redirect = NextResponse.redirect(destino);
  for (const cookie of refreshed.cookies.getAll()) {
    redirect.cookies.set(cookie);
  }
  redirect.cookies.set(FLASH_ACESSO_NEGADO, "1", {
    path: "/",
    maxAge: 15, // efêmero: só atravessa o redirect
    httpOnly: false, // o componente cliente do toast precisa ler via document.cookie
    sameSite: "lax",
  });
  redirect.headers.set("Cache-Control", "no-store");
  return redirect;
}
