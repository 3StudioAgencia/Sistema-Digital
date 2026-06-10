import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Raiz explícita do app: impede o Next de inferir a raiz do workspace por
  // lockfiles fora do repositório (ex.: pnpm-lock.yaml no home do usuário).
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
