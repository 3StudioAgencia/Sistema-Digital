/**
 * Tipos e operações do recurso /usuarios (W1-C04).
 *
 * Espelho 1:1 dos schemas do backend (apps/api .../http/usuarios.py). Os
 * VALORES dos enums são os canônicos do glossário (CLAUDE.md §6 — lowercase);
 * os RÓTULOS de UI ficam em SETOR_LABELS/LOCALIZACAO_LABELS.
 */
import { apiFetch } from "./client";

export type Setor = "studio" | "vendedor" | "motorista" | "clicheria";
export type Localizacao = "matriz" | "filial";

export const SETOR_LABELS: Record<Setor, string> = {
  studio: "3Studio",
  vendedor: "Vendedor",
  motorista: "Motorista",
  clicheria: "Clicheria",
};

export const LOCALIZACAO_LABELS: Record<Localizacao, string> = {
  matriz: "Matriz",
  filial: "Filial",
};

export type Usuario = {
  id: string;
  nome: string;
  email: string;
  setor: Setor;
  localizacao: Localizacao | null;
  administrador: boolean;
  ativo: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type PaginaUsuarios = {
  items: Usuario[];
  total: number;
  page: number;
  page_size: number;
};

export type FiltrosListagem = {
  busca?: string;
  setor?: Setor | "";
  status?: "ativo" | "inativo" | "";
  page?: number;
  pageSize?: number;
};

export type CriarUsuarioPayload = {
  nome: string;
  email: string;
  senha: string;
  setor: Setor;
  localizacao: Localizacao | null;
  administrador: boolean;
};

export type EditarUsuarioPayload = {
  nome?: string;
  setor?: Setor;
  localizacao?: Localizacao | null;
  administrador?: boolean;
};

export function listarUsuarios(
  filtros: FiltrosListagem = {},
  signal?: AbortSignal,
): Promise<PaginaUsuarios> {
  const params = new URLSearchParams();
  if (filtros.busca) params.set("busca", filtros.busca);
  if (filtros.setor) params.set("setor", filtros.setor);
  if (filtros.status) params.set("status", filtros.status);
  params.set("page", String(filtros.page ?? 1));
  params.set("page_size", String(filtros.pageSize ?? 20));
  return apiFetch<PaginaUsuarios>(`/usuarios?${params.toString()}`, { signal });
}

export function criarUsuario(payload: CriarUsuarioPayload): Promise<Usuario> {
  return apiFetch<Usuario>("/usuarios", { method: "POST", body: payload });
}

export function editarUsuario(id: string, payload: EditarUsuarioPayload): Promise<Usuario> {
  return apiFetch<Usuario>(`/usuarios/${id}`, { method: "PATCH", body: payload });
}

export function desativarUsuario(id: string): Promise<Usuario> {
  return apiFetch<Usuario>(`/usuarios/${id}/desativar`, { method: "POST" });
}

export function reativarUsuario(id: string): Promise<Usuario> {
  return apiFetch<Usuario>(`/usuarios/${id}/reativar`, { method: "POST" });
}
