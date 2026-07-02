import type { NextConfig } from "next";

// Backend FastAPI (server-only). O rewrite /api/* abaixo torna as chamadas do
// browser MESMA ORIGEM que o Next: os cookies httpOnly de sessão fluem
// automaticamente e são repassados ao backend (migração Supabase->local).
const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Raiz explícita do app: impede o Next de inferir a raiz do workspace por
  // lockfiles fora do repositório (ex.: pnpm-lock.yaml no home do usuário).
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    // /api/auth/login → <backend>/auth/login, /api/usuarios/me → <backend>/usuarios/me, ...
    return [{ source: "/api/:path*", destination: `${BACKEND}/:path*` }];
  },
};

export default nextConfig;
