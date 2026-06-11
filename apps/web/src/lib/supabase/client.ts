/**
 * Client Supabase de BROWSER (@supabase/ssr) — W1-C03.
 *
 * Substitui o createClient mínimo do W0-C01: o createBrowserClient lê/grava a
 * sessão em cookies (geridos pelo par browser+server+middleware), habilitando
 * SSR e o refresh no middleware. Singleton por aba (evita reconexões — RNF-020).
 *
 * Supabase Auth é a fonte de verdade da autenticação (emite/renova o JWT); o
 * backend FastAPI apenas VERIFICA a assinatura (CLAUDE.md §11).
 */
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { getSupabaseEnv } from "./env";

let browserClient: SupabaseClient | null = null;

export function getSupabaseBrowserClient(): SupabaseClient {
  if (browserClient) return browserClient;
  const { url, anonKey } = getSupabaseEnv();
  browserClient = createBrowserClient(url, anonKey);
  return browserClient;
}
