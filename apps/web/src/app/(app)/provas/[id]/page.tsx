import { can } from "@/lib/access-matrix";
import { fetchUsuarioAtual } from "@/lib/api/server";

import { ProvaDetalheView } from "./_components/prova-detalhe-view";

export default async function ProvaDetalhePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const usuario = await fetchUsuarioAtual();
  const perfil = usuario ? { setor: usuario.setor, administrador: usuario.administrador } : null;
  const podeCancelar = perfil ? can(perfil, "cancelar_prova") : false;
  const podeReiniciar = perfil ? can(perfil, "reiniciar_ciclo") : false;
  return (
    <ProvaDetalheView
      key={id}
      provaId={id}
      podeCancelar={podeCancelar}
      podeReiniciar={podeReiniciar}
    />
  );
}
