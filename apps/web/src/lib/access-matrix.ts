/**
 * Matriz de Acesso por Perfil — FONTE ÚNICA do frontend (W1-C05).
 *
 * Espelha a Matriz §7 (Requisitos v1.0) reconciliada com o modelo ortogonal
 * `setor` × `administrador` (ADR-023): as linhas "Exclusivo 3Studio" chaveiam
 * pelo FLAG `administrador`; as universais valem para qualquer autenticado (o
 * ESCOPO de dado — vendedor vê as próprias, motorista as "Em Trânsito" — é da
 * RLS, no C06). Lida pelo `proxy.ts` (camada superior) E pela UI (sidebar,
 * gating de ações via `can`).
 *
 * Espelho de DOMÍNIO no backend: `apps/api/src/domain/rbac.py`. O harness de
 * equivalência (`access-matrix.cells.json`) trava as duas linguagens à mesma
 * tabela — toda mudança na Matriz exige PR único cobrindo `access-matrix.ts`,
 * `rbac.py` E as migrations de RLS (regra do PR único — DAT §7.3, CLAUDE.md §5.4).
 */
import type { Setor } from "@/lib/api/usuarios";

/** Perfil derivado dos claims do JWT (pós Custom Access Token Hook). */
export type Perfil = {
  setor: Setor | null;
  administrador: boolean;
};

/** Recursos da Matriz §7 (páginas e ações sensíveis). */
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

/** Exclusivos do administrador (○ para os demais perfis) — chaveiam pelo flag. */
export const RECURSOS_ADMIN: ReadonlySet<Recurso> = new Set<Recurso>([
  "criar_prova",
  "cadastro_usuarios",
  "relatorios",
  "configuracoes",
  "log_auditoria",
  "reiniciar_ciclo",
  "cancelar_prova",
]);

/** Universais — qualquer autenticado acessa a página (●/◐; dado por RLS). */
export const RECURSOS_UNIVERSAIS: ReadonlySet<Recurso> = new Set<Recurso>([
  "dashboard",
  "escanear",
  "provas",
]);

/** Home comum a todos os perfis (Dashboard é ● na Matriz) — destino do redirect. */
export const HOME_PADRAO = "/dashboard";

/** Cookie efêmero (flash) de acesso negado, lido pelo toast no destino (DP-4). */
export const FLASH_ACESSO_NEGADO = "rbac_negado";

/**
 * Decisão de acesso por perfil ao `recurso` (nível de página/ação).
 * Recurso de admin exige o flag; universal basta estar autenticado.
 */
export function can(perfil: Perfil, recurso: Recurso): boolean {
  if (RECURSOS_ADMIN.has(recurso)) return perfil.administrador;
  if (RECURSOS_UNIVERSAIS.has(recurso)) return true;
  return false; // recurso desconhecido: negação por padrão
}

/** Rota (prefixo) → recurso da Matriz. Ordem: prefixo mais específico primeiro. */
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

/**
 * Recurso correspondente à rota, ou `null` quando a rota não é gateada pela
 * Matriz (ex.: `/informacoes`, raiz do grupo) — essas são neutras: basta estar
 * autenticado (a proteção de autenticação é do layout `getUser()`).
 */
export function recursoDaRota(pathname: string): Recurso | null {
  for (const { prefixo, recurso } of ROTAS) {
    if (pathname === prefixo || pathname.startsWith(`${prefixo}/`)) return recurso;
  }
  return null;
}

/** Decisão da camada superior: rota neutra → liberada; rota da Matriz → `can`. */
export function podeAcessarRota(perfil: Perfil, pathname: string): boolean {
  const recurso = recursoDaRota(pathname);
  if (recurso === null) return true;
  return can(perfil, recurso);
}

/** Deriva o `Perfil` dos claims do JWT (setor/administrador elevados pelo hook). */
export function perfilDeClaims(claims: Record<string, unknown> | null | undefined): Perfil {
  const setorClaim = claims?.["setor"];
  const setor = typeof setorClaim === "string" ? (setorClaim as Setor) : null;
  // O hook injeta `administrador` como boolean JSON; nunca conceder por omissão.
  const administrador = claims?.["administrador"] === true;
  return { setor, administrador };
}
