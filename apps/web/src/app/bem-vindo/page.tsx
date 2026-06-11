import { redirect } from "next/navigation";

import { getSupabaseServerClient } from "@/lib/supabase/server";

import { Welcome } from "../_components/welcome";

export const dynamic = "force-dynamic";

/**
 * Boas-vindas (W1-C03 / DP-7) — fluxo mobile: hero + "Seja bem vindo!" + Entrar.
 * Já autenticado → /inicio. No desktop, <Welcome> encaminha para /login (a tela
 * de boas-vindas é mobile-only; desktop vai direto ao split).
 */
export default async function BemVindoPage() {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect("/inicio");
  return <Welcome />;
}
