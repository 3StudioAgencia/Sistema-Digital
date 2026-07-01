import { Suspense } from "react";

import { escopoDeProvas } from "@/lib/api/provas";
import { fetchUsuarioAtual } from "@/lib/api/server";

import { ProvasView } from "./_components/provas-view";

export default async function ProvasPage() {
  const usuario = await fetchUsuarioAtual();
  const escopo = escopoDeProvas(usuario);
  return (
    <Suspense fallback={null}>
      <ProvasView escopo={escopo} />
    </Suspense>
  );
}
