import { redirect } from "next/navigation";

import { AppShell } from "@/components/shell/AppShell";
import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { fetchUsuarioAtual } from "@/lib/api/server";
import { lerSessao } from "@/lib/auth/session";

import { InactivityGuard } from "../_components/inactivity-guard";
import { RbacFlash } from "../_components/rbac-flash";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // Proteção server-side de TODO o grupo (app): sem sessão válida → /login.
  const sessao = await lerSessao();
  if (!sessao) redirect("/login");

  const usuario = await fetchUsuarioAtual();
  const emailSessao = typeof sessao.email === "string" ? sessao.email : "";

  return (
    <ToastProvider>
      <InactivityGuard />
      <RbacFlash />
      <AppShell usuario={usuario} emailSessao={emailSessao}>
        {children}
      </AppShell>
    </ToastProvider>
  );
}
