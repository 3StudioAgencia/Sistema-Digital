/**
 * Client Supabase de SERVIDOR (@supabase/ssr) — W1-C03.
 *
 * Para Server Components, Route Handlers e Server Actions. Lê os cookies da
 * requisição via next/headers. A escrita de cookies a partir de um Server
 * Component lança (read-only) e é ignorada de propósito — o refresh de sessão
 * é responsabilidade do middleware (updateSession), padrão @supabase/ssr.
 *
 * Para PROTEÇÃO use sempre supabase.auth.getUser() (valida no servidor de
 * auth), nunca getSession() (DP-1 / prompt §3.2).
 */
import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

import { getSupabaseEnv } from "./env";

export async function getSupabaseServerClient(): Promise<SupabaseClient> {
  const { url, anonKey } = getSupabaseEnv();
  const cookieStore = await cookies();

  return createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Server Component: cookies são read-only. O middleware renova a
          // sessão e grava os cookies — ignorar aqui é seguro (@supabase/ssr).
        }
      },
    },
  });
}
