import { redirect } from "next/navigation";

/**
 * Rota legada do W1-C03 (landing placeholder) — agora a plataforma autenticada
 * vive no app shell (W1-C04). Mantida como redirect para não quebrar links e
 * fluxos antigos; o C05 definirá a "página inicial do perfil".
 */
export default function InicioPage() {
  redirect("/usuarios");
}
