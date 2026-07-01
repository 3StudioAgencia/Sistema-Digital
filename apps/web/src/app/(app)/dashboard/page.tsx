import { can, type Perfil } from "@/lib/access-matrix";
import { fetchDashboard, fetchUsuarioAtual } from "@/lib/api/server";

import { DashboardView } from "./_components/dashboard-view";

export default async function DashboardPage() {
  const [usuario, inicial] = await Promise.all([fetchUsuarioAtual(), fetchDashboard()]);
  const perfil: Perfil = {
    setor: usuario?.setor ?? null,
    administrador: usuario?.administrador ?? false,
  };
  return <DashboardView inicial={inicial} podeCriarProva={can(perfil, "criar_prova")} />;
}
