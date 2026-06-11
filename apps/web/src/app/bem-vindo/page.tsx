import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

/**
 * `/bem-vindo` foi absorvido pelo `/login` adaptativo (as boas-vindas viraram o
 * primeiro passo do fluxo mobile dentro do /login — DP-7). Mantido como
 * redirecionamento para não quebrar links antigos.
 */
export default function BemVindoPage() {
  redirect("/login");
}
