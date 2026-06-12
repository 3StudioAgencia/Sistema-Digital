import { redirect } from "next/navigation";

import { HOME_PADRAO } from "@/lib/access-matrix";

/**
 * Rota legada do W1-C03 (landing placeholder) — agora a plataforma autenticada
 * vive no app shell (W1-C04). Mantida como redirect para não quebrar links e
 * fluxos antigos; aponta para a home do perfil (HOME_PADRAO = /dashboard, C05).
 */
export default function InicioPage() {
  redirect(HOME_PADRAO);
}
