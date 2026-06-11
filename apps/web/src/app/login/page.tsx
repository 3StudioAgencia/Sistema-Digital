import { redirect } from "next/navigation";

import { getSupabaseServerClient } from "@/lib/supabase/server";

import { AuthFlow } from "../_components/auth-flow";

export const dynamic = "force-dynamic";

/**
 * Tela de login (W1-C03) — experiência adaptativa em `<AuthFlow>`:
 * - desktop (>=768px): split com a imagem-herói (formato custom) + formulário;
 * - mobile: boas-vindas primeiro e o formulário ao clicar em "Entrar" (mesmo /login).
 *
 * Já autenticado → /inicio. O notice de inatividade chega por ?expirado=1 (DP-3).
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect("/inicio");

  const sp = await searchParams;
  return <AuthFlow expired={sp.expirado === "1"} />;
}
