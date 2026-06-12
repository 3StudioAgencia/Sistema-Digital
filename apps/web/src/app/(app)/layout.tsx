import { redirect } from "next/navigation";

import { AppShell } from "@/components/shell/AppShell";
import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { fetchUsuarioAtual } from "@/lib/api/server";
import { getSupabaseServerClient } from "@/lib/supabase/server";

import { InactivityGuard } from "../_components/inactivity-guard";
import { RbacFlash } from "../_components/rbac-flash";

export const dynamic = "force-dynamic";

/**
 * Layout do grupo autenticado (W1-C04 / ADR-026) — o app shell da plataforma.
 *
 * Proteção no servidor com getUser() (nunca getSession — CLAUDE.md §5.4). O
 * enforcement por PERFIL é do proxy (camada superior, W1-C05); aqui montamos o
 * RbacFlash, que transforma o redirect de acesso negado em toast. A linha de
 * domínio (/usuarios/me) alimenta saudação/rodapé e a visibilidade do menu por
 * perfil, degradando para fallback de e-mail se a API estiver fora ou o usuário
 * ainda não foi provisionado.
 */
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
