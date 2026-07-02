/**
 * Refresh de sessão + enforcement de RBAC no proxy do App Router (auth própria).
 *
 * Migração Supabase->local: substitui o `updateSession` do @supabase/ssr. A cada
 * NAVEGAÇÃO de página (o matcher exclui /api e estáticos):
 * - verifica o cookie `access_token` localmente (ES256 + chave pública — `jose`);
 * - se expirado mas há `refresh_token`, RENOVA no backend (/auth/refresh) e
 *   repassa os novos cookies (mantém a sessão viva sem novo login);
 * - decide o RBAC superior via `perfilDeClaims`/`podeAcessarRota` (inalterados);
 *   acesso negado → 302 para a home + cookie de flash que o toast lê no destino.
 *
 * Sem sessão NÃO redireciona aqui — o guard SSR do layout decide /login. As
 * chamadas /api/* vão direto ao backend (rewrite do next.config), que faz a auth.
 */
import { type NextRequest, NextResponse } from "next/server";
import type { JWTPayload } from "jose";

import {
  FLASH_ACESSO_NEGADO,
  HOME_PADRAO,
  perfilDeClaims,
  podeAcessarRota,
} from "@/lib/access-matrix";
import { ACCESS_COOKIE, REFRESH_COOKIE, verificarToken } from "@/lib/auth/verify";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const response = NextResponse.next({ request });
  // Respostas com Set-Cookie de refresh NÃO podem ser cacheadas (serviriam a
  // sessão de um usuário a outro — §3.5).
  response.headers.set("Cache-Control", "no-store");

  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  let claims: JWTPayload | null = access ? await verificarToken(access) : null;
  let setCookies: string[] = [];

  if (!claims && request.cookies.get(REFRESH_COOKIE)?.value) {
    const renovado = await renovarSessao(request);
    claims = renovado.claims;
    setCookies = renovado.setCookies;
    for (const sc of setCookies) response.headers.append("set-cookie", sc);
  }

  if (claims) {
    const perfil = perfilDeClaims(claims as Record<string, unknown>);
    if (!podeAcessarRota(perfil, request.nextUrl.pathname)) {
      return redirectAcessoNegado(request, setCookies);
    }
  }
  return response;
}

async function renovarSessao(
  request: NextRequest,
): Promise<{ claims: JWTPayload | null; setCookies: string[] }> {
  try {
    const backendResp = await fetch(`${BACKEND}/auth/refresh`, {
      method: "POST",
      headers: { cookie: request.headers.get("cookie") ?? "" },
      cache: "no-store",
    });
    if (!backendResp.ok) return { claims: null, setCookies: [] };
    const setCookies = backendResp.headers.getSetCookie();
    const novoAccess = valorDoCookie(setCookies, ACCESS_COOKIE);
    const claims = novoAccess ? await verificarToken(novoAccess) : null;
    return { claims, setCookies };
  } catch {
    return { claims: null, setCookies: [] };
  }
}

function valorDoCookie(setCookies: string[], nome: string): string | null {
  for (const sc of setCookies) {
    const m = sc.match(new RegExp(`^${nome}=([^;]*)`));
    if (m) return m[1];
  }
  return null;
}

function redirectAcessoNegado(request: NextRequest, setCookies: string[]): NextResponse {
  const destino = request.nextUrl.clone();
  destino.pathname = HOME_PADRAO;
  destino.search = "";
  const redirect = NextResponse.redirect(destino);
  // Preserva os cookies da sessão recém-renovada no redirect.
  for (const sc of setCookies) redirect.headers.append("set-cookie", sc);
  redirect.cookies.set(FLASH_ACESSO_NEGADO, "1", {
    path: "/",
    maxAge: 15, // efêmero: só atravessa o redirect
    httpOnly: false, // o componente cliente do toast precisa ler via document.cookie
    sameSite: "lax",
  });
  redirect.headers.set("Cache-Control", "no-store");
  return redirect;
}

export const config = {
  matcher: [
    // Exclui /api (vai direto ao backend via rewrite — o backend faz a auth) e
    // os estáticos. O proxy cuida só das navegações de página (refresh + RBAC).
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|ico)$).*)",
  ],
};
