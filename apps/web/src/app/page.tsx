import { redirect } from "next/navigation";

import { HOME_PADRAO } from "@/lib/access-matrix";
import { getSupabaseServerClient } from "@/lib/supabase/server";

// Usa cookies (getUser) → renderização dinâmica; nunca prerenderizada no build.
export const dynamic = "force-dynamic";

/**
 * Raiz — porta de entrada (W1-C03 / W1-C04).
 *
 * Autenticado → home do perfil (HOME_PADRAO = /dashboard, ● a todos na Matriz §7).
 * Não autenticado → /login. A proteção usa getUser() (valida no servidor de auth),
 * nunca getSession() (§3.2).
 */
export default async function Home() {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  redirect(user ? HOME_PADRAO : "/login");
}
