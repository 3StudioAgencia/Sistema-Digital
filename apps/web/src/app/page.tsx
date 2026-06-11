import { redirect } from "next/navigation";

import { getSupabaseServerClient } from "@/lib/supabase/server";

// Usa cookies (getUser) → renderização dinâmica; nunca prerenderizada no build.
export const dynamic = "force-dynamic";

/**
 * Raiz — porta de entrada (W1-C03 / DP-4, DP-7).
 *
 * Autenticado → /inicio. Não autenticado → /bem-vindo (que no mobile mostra as
 * boas-vindas e no desktop encaminha para o /login em split). A proteção usa
 * getUser() (valida no servidor de auth), nunca getSession() (§3.2).
 */
export default async function Home() {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  redirect(user ? "/inicio" : "/bem-vindo");
}
