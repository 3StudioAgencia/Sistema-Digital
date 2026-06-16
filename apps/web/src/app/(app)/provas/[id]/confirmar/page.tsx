import { ConfirmarView } from "./_components/confirmar-view";

/**
 * Confirmação da movimentação (destino pós-identificação do W3-C10 — DP-2).
 *
 * Server component fino: extrai o `id` do route param (Next 16: `params` é
 * Promise) e delega ao client view, que busca o detalhe (`GET /provas/{id}`,
 * universal-em-escopo) e mostra nome + requerimento + um PLACEHOLDER de
 * assinatura. Aqui o C11 (validar a próxima transição) e o C12 (captura de
 * assinatura) plugam o fluxo — o C10 só identifica.
 */
export default async function ConfirmarProvaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ConfirmarView key={id} provaId={id} />;
}
