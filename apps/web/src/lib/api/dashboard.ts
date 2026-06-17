/**
 * Tipos e operação do recurso /dashboard (W4-C16).
 *
 * Espelho 1:1 do ``DashboardOut`` do backend (apps/api .../http/dashboard.py).
 * Os contadores são escopados pela RLS (cada perfil vê só os seus números —
 * Matriz §7); ``atrasadas_por_vendedor`` já vem ordenado por contagem desc.
 *
 * Princípio do mínimo de requisições (RNF-020/021): a carga inicial é SSR (server
 * fetch no ``page.tsx``); este ``fetchDashboard`` é o REFETCH disparado (debounced)
 * pela ÚNICA subscription Realtime do painel — sem polling.
 */
import { apiFetch } from "./client";

export type AtrasadaVendedor = {
  vendedor_id: string;
  /** Resolvido pela projeção SECURITY DEFINER (escopada); `null` no caso degenerado. */
  vendedor_nome: string | null;
  total: number;
};

export type Dashboard = {
  criadas_hoje: number;
  com_vendedor: number;
  aprovadas: number;
  na_clicheria: number;
  atrasadas_total: number;
  atrasadas_por_vendedor: AtrasadaVendedor[];
};

/** Refetch dos contadores (client) — chamado após eventos Realtime de `provas`. */
export function fetchDashboard(signal?: AbortSignal): Promise<Dashboard> {
  return apiFetch<Dashboard>("/dashboard", { signal });
}
