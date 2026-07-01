import { redirect } from "next/navigation";

import { AppShell } from "@/components/shell/AppShell";
import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { fetchUsuarioAtual } from "@/lib/api/server";
import { getSupabaseServerClient } from "@/lib/supabase/server";

import { InactivityGuard } from "../_components/inactivity-guard";
import { RbacFlash } from "../_components/rbac-flash";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const usuario = await fetchUsuarioAtual();

  return (
    <ToastProvider>
      <InactivityGuard />
      <RbacFlash />
      <AppShell usuario={usuario} emailSessao={user.email ?? ""}>
        {children}
      </AppShell>
    </ToastProvider>
  );
}
