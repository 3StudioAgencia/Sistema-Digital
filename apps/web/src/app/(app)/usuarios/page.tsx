import { UsuariosView } from "./_components/usuarios-view";

export const dynamic = "force-dynamic";

/**
 * Gerenciador de usuários (W1-C04) — primeira página real dentro do app shell.
 *
 * Os dados vêm SEMPRE do backend (guard de admin — DP-5), nunca de leitura
 * direta do client Supabase no browser (§3.10 do prompt). Quem não é admin
 * recebe a negação do backend (403) renderizada como estado de acesso restrito;
 * o enforcement de rota por perfil chega no C05.
 */
export default function UsuariosPage() {
  return <UsuariosView />;
}
