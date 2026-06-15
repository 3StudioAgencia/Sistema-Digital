import { ProvaDetalheView } from "./_components/prova-detalhe-view";

/**
 * Detalhe da prova (W2-C08) — destino do "Ver" da listagem (DP-6).
 *
 * Server component fino: extrai o `id` do route param (Next 16: `params` é
 * Promise) e delega ao client view, que busca via `apiFetch` (mesmo padrão do
 * C07), exibe a arte por proxy do backend (DP-5) e trata 404 com redirect +
 * toast — sem revelar se a prova existe (anti-enumeração — §11). A rota cai no
 * recurso universal `provas` na Matriz §7; o ESCOPO de dado é da RLS, no servidor.
 */
export default async function ProvaDetalhePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // `key={id}`: navegar entre provas REMONTA o view (estado fresco — sem resets
  // síncronos de estado dentro de efeitos; o skeleton reaparece a cada prova).
  return <ProvaDetalheView key={id} provaId={id} />;
}
