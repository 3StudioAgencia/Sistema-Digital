import type { Metadata } from "next";
import localFont from "next/font/local";

import "./globals.css";

// Inter self-hospedada (next/font/local): build HERMÉTICO (sem rede em build —
// alinhado à decisão do W0), zero layout shift e bom para o futuro on-prem.
// Pesos do design (Figma): 300 Light · 400 Regular · 600 Semi Bold.
const inter = localFont({
  src: [
    { path: "./fonts/inter-latin-300-normal.woff2", weight: "300", style: "normal" },
    { path: "./fonts/inter-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "./fonts/inter-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Rastreio de Provas Digitais · 3Studio",
  description:
    "Controle e rastreabilidade do fluxo físico-digital de provas de impressão — da criação à clicheria.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
