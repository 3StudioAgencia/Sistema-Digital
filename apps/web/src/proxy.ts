/**
 * Proxy do App Router (Next 16 — sucede o antigo `middleware.ts`).
 *
 * - W1-C03: refresh de sessão.
 * - W1-C05: enforcement de RBAC por perfil (camada superior, CLAUDE.md §5.4) —
 *   feito dentro de `updateSession`, após o refresh, lendo `lib/access-matrix.ts`
 *   (claims via getClaims() local; acesso negado → redirect + flash de toast).
 *
 * (Nota: "middleware" nos documentos = este `proxy.ts` no Next 16 — ADR-021.)
 */
import { type NextRequest, type NextResponse } from "next/server";

import { updateSession } from "@/lib/supabase/middleware";

export async function proxy(request: NextRequest): Promise<NextResponse> {
  return await updateSession(request);
}

export const config = {
  // Exclui assets estáticos e imagens: performance e para o no-store do refresh
  // não afetar o cache de assets imutáveis.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|ico)$).*)",
  ],
};
