import {
  ChartColumn,
  House,
  Info,
  Laptop,
  Plus,
  QrCode,
  ScrollText,
  Settings,
  UserRound,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  rotulo: string;
  icone: LucideIcon;
  componente?: string;
};

export const NAV_PRINCIPAL: NavItem[] = [
  { href: "/dashboard", rotulo: "Dashboard", icone: House, componente: "C16" },
  { href: "/provas", rotulo: "Provas", icone: Laptop, componente: "C07" },
  { href: "/provas/nova", rotulo: "Nova prova", icone: Plus, componente: "C06" },
  { href: "/escanear", rotulo: "Escanear", icone: QrCode, componente: "C10" },
  { href: "/relatorios", rotulo: "Relatórios", icone: ChartColumn, componente: "C17" },
  { href: "/usuarios", rotulo: "Usuários", icone: UserRound },
];

export const NAV_SECUNDARIA: NavItem[] = [
  { href: "/auditoria", rotulo: "Auditoria", icone: ScrollText, componente: "C20" },
  { href: "/configuracoes", rotulo: "Configurações", icone: Settings },
];

export function hrefAtivo(pathname: string): string | null {
  const todos = [...NAV_PRINCIPAL, ...NAV_SECUNDARIA];
  let melhor: string | null = null;
  for (const item of todos) {
    const casa = pathname === item.href || pathname.startsWith(`${item.href}/`);
    if (casa && (melhor === null || item.href.length > melhor.length)) {
      melhor = item.href;
    }
  }
  return melhor;
}
