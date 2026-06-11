import { redirect } from "next/navigation";

import { getSupabaseServerClient } from "@/lib/supabase/server";

import { LoginPanel } from "../_components/login-panel";
import styles from "./login.module.css";

export const dynamic = "force-dynamic";

/**
 * Tela de login (W1-C03) — adaptativa:
 * - desktop (≥768px): split com a imagem-herói à esquerda e o formulário à direita;
 * - mobile: formulário em coluna centrada sobre fundo preto.
 *
 * Já autenticado → /inicio. O notice de inatividade chega por ?expirado=1 (DP-3),
 * lido aqui no servidor e repassado ao painel (evita useSearchParams/Suspense).
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

  return (
    <div className={styles.split}>
      <div className={styles.hero} aria-hidden="true" />
      <div className={styles.formArea}>
        <LoginPanel expired={sp.expirado === "1"} />
      </div>
    </div>
  );
}
