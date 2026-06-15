import { Suspense } from "react";

import { escopoDeProvas } from "@/lib/api/provas";
import { fetchUsuarioAtual } from "@/lib/api/server";

import { ProvasView } from "./_components/provas-view";

/**
 * Provas digitais (W2-C07) — listagem/busca/filtros da operação diária.
 *
 * Server component: resolve o ESCOPO do perfil (DP-2) a partir da linha de
 * domínio (degrada para "todas" se a API estiver fora — a RLS ainda escopa os
 * dados no servidor). `<ProvasView>` usa `useSearchParams` (estado de filtros na
 * URL — DP-5), por isso vive sob `<Suspense>`.
 */
export default async function ProvasPage() {
  const usuario = await fetchUsuarioAtual();
  const escopo = escopoDeProvas(usuario);
  return (
    <Suspense fallback={null}>
      <ProvasView escopo={escopo} />
    </Suspense>
  );
}
