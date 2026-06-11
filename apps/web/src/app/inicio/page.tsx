import { redirect } from "next/navigation";

import { getSupabaseServerClient } from "@/lib/supabase/server";

import { AuthProof } from "../_components/auth-proof";
import { InactivityGuard } from "../_components/inactivity-guard";
import styles from "./inicio.module.css";

export const dynamic = "force-dynamic";

/**
 * Landing autenticada PLACEHOLDER (W1-C03 / DP-4).
 *
 * Substituída pelo roteamento por perfil (C05) e dashboard (C16). Protegida no
 * servidor com getUser() (§3.2). Monta o guarda de inatividade de 30 min (DP-3)
 * e a prova viva da cadeia de auth (AuthProof → backend /auth/me).
 */
export default async function InicioPage() {
  const supabase = await getSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <main className={styles.page}>
      <InactivityGuard />
      <section className={styles.card}>
        {/* eslint-disable-next-line @next/next/no-img-element -- SVG estático; next/image não otimiza SVG */}
        <img
          src="/logo-3studio.svg"
          alt="3Studio"
          width={122}
          height={26}
          className={styles.wordmark}
        />
        <h1 className={styles.title}>Você está autenticado</h1>
        <p className={styles.lead}>
          Landing placeholder do W1-C03. O roteamento por perfil chega no C05 e o dashboard no C16.
        </p>
        <AuthProof />
      </section>
    </main>
  );
}
