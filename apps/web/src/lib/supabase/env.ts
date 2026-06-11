/**
 * Leitura+validação das variáveis públicas do Supabase (W1-C03).
 *
 * Reusada pelos três clients (browser/server/middleware) para uma única fonte
 * de verdade e mensagem de erro consistente. As variáveis NEXT_PUBLIC_* são
 * embutidas no bundle do browser e públicas por design — o acesso a dados é
 * controlado pela RLS (camada inferior do RBAC, CLAUDE.md §5.4). A chave
 * preenchida é a *publishable* moderna do projeto (DP-2).
 */
export interface SupabaseEnv {
  url: string;
  anonKey: string;
}

export function getSupabaseEnv(): SupabaseEnv {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error(
      "Supabase não configurado: defina NEXT_PUBLIC_SUPABASE_URL e " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY (ver apps/web/.env.example).",
    );
  }
  return { url, anonKey };
}
