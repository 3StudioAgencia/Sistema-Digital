import { Suspense } from "react";

import { RelatoriosView } from "./_components/relatorios-view";

/**
 * Relatórios gerenciais (W5-C17) — exclusivo do 3Studio (a rota é gateada pelo
 * proxy + a sidebar esconde o item; os endpoints respondem 403 ao não-admin — DP-7).
 *
 * `<RelatoriosView>` usa `useSearchParams` (aba + filtros na URL — DP-4), por isso
 * vive sob `<Suspense>`. A agregação é client-lazy por aba (DP-6) — sem SSR de dado
 * aqui (é um snapshot dirigido por filtro, não a landing page).
 */
export default function RelatoriosPage() {
  return (
    <Suspense fallback={null}>
      <RelatoriosView />
    </Suspense>
  );
}
