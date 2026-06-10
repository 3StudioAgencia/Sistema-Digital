/**
 * Client Supabase mínimo — SOMENTE configuração (W0-C01).
 *
 * A autenticação (login, sessão, guards) chega na Wave 1/C03, que também
 * adicionará o client de servidor com cookies (@supabase/ssr) para o App
 * Router e o middleware RBAC. Nada de lógica de auth aqui.
 *
 * O Supabase Auth é a fonte de verdade da autenticação: emite e renova os
 * JWTs; o backend FastAPI apenas VERIFICA a assinatura (CLAUDE.md §11).
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null = null;

/**
 * Client de browser (singleton por aba — evita reconexões desnecessárias,
 * RNF-020). Lazy: o build não exige as variáveis; o uso em runtime sim.
 */
export function getSupabaseBrowserClient(): SupabaseClient {
  if (browserClient) return browserClient;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error(
      "Supabase não configurado: defina NEXT_PUBLIC_SUPABASE_URL e " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY (ver apps/web/.env.example).",
    );
  }

  browserClient = createClient(url, anonKey);
  return browserClient;
}
