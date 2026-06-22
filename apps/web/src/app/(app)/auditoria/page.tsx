import { Suspense } from "react";

import { AuditoriaView } from "./_components/auditoria-view";

/**
 * Log de Auditoria (W6-C20) — exclusivo do 3Studio (a rota é gateada pelo proxy +
 * a sidebar esconde o item; o endpoint responde 403 ao não-admin — duas camadas).
 *
 * `<AuditoriaView>` usa `useSearchParams` (filtros na URL — reusa o C07), por isso
 * vive sob `<Suspense>`. A consulta é client-side dirigida por filtro (snapshot do
 * log, não landing page) — sem SSR de dado aqui.
 */
export default function AuditoriaPage() {
  return (
    <Suspense fallback={null}>
      <AuditoriaView />
    </Suspense>
  );
}
