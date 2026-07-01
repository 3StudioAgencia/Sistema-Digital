import { Suspense } from "react";

import { AuditoriaView } from "./_components/auditoria-view";

export default function AuditoriaPage() {
  return (
    <Suspense fallback={null}>
      <AuditoriaView />
    </Suspense>
  );
}
