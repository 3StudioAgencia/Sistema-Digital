/**
 * Verificação local do access token ES256 (migração Supabase->local).
 *
 * Usado pelo proxy (Edge) e pelo SSR (Node) — daí ser AGNÓSTICO de runtime (só
 * `jose`, sem `next/headers`). Verifica assinatura + audience + expiração com a
 * chave PÚBLICA (`AUTH_JWT_PUBLIC_KEY`, base64 do PEM). É a defesa em profundidade
 * do RBAC superior; o backend revalida tudo a cada chamada de API.
 */
import { importSPKI, jwtVerify, type JWTPayload } from "jose";

export const ACCESS_COOKIE = "access_token";
export const REFRESH_COOKIE = "refresh_token";

const ALG = "ES256";
const AUDIENCE = "authenticated";

function pemDeBase64(b64: string): string {
  // Base64 do PEM (linha única no ambiente) → texto PEM. `atob` no Edge; `Buffer`
  // no Node. O PEM é ASCII, então a decodificação byte-a-byte do atob preserva-o.
  return typeof atob === "function" ? atob(b64) : Buffer.from(b64, "base64").toString("utf-8");
}

let chaveCache: ReturnType<typeof importSPKI> | null = null;
function chavePublica(): ReturnType<typeof importSPKI> {
  if (!chaveCache) {
    const b64 = process.env.AUTH_JWT_PUBLIC_KEY;
    if (!b64) throw new Error("AUTH_JWT_PUBLIC_KEY não configurada (chave pública ES256).");
    chaveCache = importSPKI(pemDeBase64(b64), ALG);
  }
  return chaveCache;
}

/** Verifica o token; devolve os claims ou `null` (inválido/expirado/malformado). */
export async function verificarToken(token: string): Promise<JWTPayload | null> {
  try {
    const { payload } = await jwtVerify(token, await chavePublica(), {
      algorithms: [ALG],
      audience: AUDIENCE,
    });
    return payload;
  } catch {
    return null;
  }
}
