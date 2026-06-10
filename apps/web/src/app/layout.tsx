import type { Metadata } from "next";
import "./globals.css";

// Sem next/font/google: fonte de sistema mantém o build hermético (sem rede)
// e a primeira pintura leve — alinhado ao pilar de animações/UI leves.
export const metadata: Metadata = {
  title: "Rastreio de Provas Digitais · 3Studio",
  description:
    "Controle e rastreabilidade do fluxo físico-digital de provas de impressão — da criação à clicheria.",
};

// TODO(Wave 1/C05): o middleware RBAC viverá em src/middleware.ts e a matriz
// determinística em src/lib/access-matrix.ts (CLAUDE.md §5.4). Não criar antes.
// TODO(Wave 6/C19): tokens de animação em src/lib/motion/tokens.ts.

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
