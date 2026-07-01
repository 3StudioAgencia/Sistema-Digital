import type { Setor } from "@/lib/api/usuarios";

export type Perfil = {
  setor: Setor | null;
  administrador: boolean;
};

export type Recurso =
  | "dashboard"
  | "escanear"
  | "provas"
  | "criar_prova"
  | "cadastro_usuarios"
  | "relatorios"
  | "configuracoes"
  | "log_auditoria"
  | "reiniciar_ciclo"
  | "cancelar_prova";

export const RECURSOS_ADMIN: ReadonlySet<Recurso> = new Set<Recurso>([
  "criar_prova",
  "cadastro_usuarios",
  "relatorios",
  "configuracoes",
  "log_auditoria",
  "reiniciar_ciclo",
  "cancelar_prova",
]);

export const RECURSOS_UNIVERSAIS: ReadonlySet<Recurso> = new Set<Recurso>([
  "dashboard",
  "escanear",
  "provas",
]);

export const HOME_PADRAO = "/dashboard";
export const FLASH_ACESSO_NEGADO = "rbac_negado";
export function can(perfil: Perfil, recurso: Recurso): boolean {
  if (RECURSOS_ADMIN.has(recurso)) return perfil.administrador;
  if (RECURSOS_UNIVERSAIS.has(recurso)) return true;
  return false;
}

const ROTAS: readonly { prefixo: string; recurso: Recurso }[] = [
  { prefixo: "/provas/nova", recurso: "criar_prova" },
  { prefixo: "/provas", recurso: "provas" },
  { prefixo: "/usuarios", recurso: "cadastro_usuarios" },
  { prefixo: "/relatorios", recurso: "relatorios" },
  { prefixo: "/configuracoes", recurso: "configuracoes" },
  { prefixo: "/auditoria", recurso: "log_auditoria" },
  { prefixo: "/dashboard", recurso: "dashboard" },
  { prefixo: "/escanear", recurso: "escanear" },
];

export function recursoDaRota(pathname: string): Recurso | null {
  for (const { prefixo, recurso } of ROTAS) {
    if (pathname === prefixo || pathname.startsWith(`${prefixo}/`)) return recurso;
  }
  return null;
}

export function podeAcessarRota(perfil: Perfil, pathname: string): boolean {
  const recurso = recursoDaRota(pathname);
  if (recurso === null) return true;
  return can(perfil, recurso);
}

export function perfilDeClaims(claims: Record<string, unknown> | null | undefined): Perfil {
  const setorClaim = claims?.["setor"];
  const setor = typeof setorClaim === "string" ? (setorClaim as Setor) : null;
  const administrador = claims?.["administrador"] === true;
  return { setor, administrador };
}
