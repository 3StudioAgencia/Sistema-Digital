import { Suspense } from "react";

import { RelatoriosView } from "./_components/relatorios-view";

export default function RelatoriosPage() {
  return (
    <Suspense fallback={null}>
      <RelatoriosView />
    </Suspense>
  );
}
