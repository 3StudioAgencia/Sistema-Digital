/**
 * Proxy do App Router (Next 16 — sucede o antigo `middleware.ts`) — W1-C03:
 * SOMENTE refresh de sessão.
 *
 * O enforcement de RBAC (camada superior, CLAUDE.md §5.4) entra AQUI no
 * W1-C05 — após o refresh, lendo lib/access-matrix.ts. NÃO adicionar guards de
 * rota nesta wave. (Nota: "middleware" nos documentos = este `proxy.ts` no
 * Next 16 — ver ADR de auth/sessão.)
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
