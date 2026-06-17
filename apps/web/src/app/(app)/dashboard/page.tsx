import { can, type Perfil } from "@/lib/access-matrix";
import { fetchDashboard, fetchUsuarioAtual } from "@/lib/api/server";

import { DashboardView } from "./_components/dashboard-view";

/**
 * Dashboard (W4-C16) — visibilidade operacional em tempo real, fiel ao design.
 *
 * Server component: resolve o PERFIL (para os atalhos role-aware — DP-3) e faz a
 * carga INICIAL dos contadores no servidor (sem waterfall no cliente — RNF-001).
 * O ESCOPO dos números é da RLS de `provas` (no backend); aqui o perfil só decide
 * quais ATALHOS aparecem. Ambas as buscas degradam para null/false sem derrubar a
 * página (a RLS continua escopando os dados).
 */
export default async function DashboardPage() {
  const [usuario, inicial] = await Promise.all([fetchUsuarioAtual(), fetchDashboard()]);
  const perfil: Perfil = {
    setor: usuario?.setor ?? null,
    administrador: usuario?.administrador ?? false,
  };
  return <DashboardView inicial={inicial} podeCriarProva={can(perfil, "criar_prova")} />;
}
