"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getSupabaseBrowserClient } from "@/lib/supabase/client";

import styles from "../inicio/inicio.module.css";

interface Me {
  sub: string;
  email: string | null;
  role: string | null;
}

/**
 * Prova viva da cadeia de auth ponta-a-ponta (W1-C03 / DP-4): pega o access
 * token da sessão (browser) e chama o backend GET /auth/me, que VERIFICA o JWT
 * (ES256/JWKS+HS256) e devolve a identidade. Também oferece o "Sair".
 */
export function AuthProof() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      const supabase = getSupabaseBrowserClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        if (active) setError("Sessão ausente — entre novamente.");
        return;
      }
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (!res.ok) {
          if (active) setError(`O backend recusou o token (HTTP ${res.status}).`);
          return;
        }
        const data: Me = await res.json();
        if (active) setMe(data);
      } catch {
        if (active) setError("Não foi possível contatar a API.");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function sair() {
    const supabase = getSupabaseBrowserClient();
    await supabase.auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <>
      {me && (
        <dl className={styles.identity}>
          <dt>sub</dt>
          <dd>{me.sub}</dd>
          <dt>email</dt>
          <dd>{me.email ?? "—"}</dd>
          <dt>role</dt>
          <dd>{me.role ?? "—"}</dd>
        </dl>
      )}
      {!me && !error && <p className={styles.muted}>Verificando o token no backend…</p>}
      {error && <p className={styles.error}>{error}</p>}
      <button type="button" className={styles.sair} onClick={sair}>
        Sair
      </button>
    </>
  );
}
