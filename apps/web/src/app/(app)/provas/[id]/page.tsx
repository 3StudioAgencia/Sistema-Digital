import { can } from "@/lib/access-matrix";
import { fetchUsuarioAtual } from "@/lib/api/server";

import { ProvaDetalheView } from "./_components/prova-detalhe-view";

/**
 * Detalhe da prova (W2-C08) — destino do "Ver" da listagem (DP-6).
 *
 * Server component fino: extrai o `id` do route param (Next 16: `params` é
 * Promise) e delega ao client view, que busca via `apiFetch` (mesmo padrão do
 * C07), exibe a arte por proxy do backend (DP-5) e trata 404 com redirect +
 * toast — sem revelar se a prova existe (anti-enumeração — §11). A rota cai no
 * recurso universal `provas` na Matriz §7; o ESCOPO de dado é da RLS, no servidor.
 *
 * W3-C14: resolve no SERVIDOR (sem ida extra ao backend — `fetchUsuarioAtual` é
 * memoizado por requisição) se este perfil pode CANCELAR (Matriz §7 →
 * `can(perfil, "cancelar_prova")` = flag `administrador`) e passa o booleano ao
 * view, que mostra a ação destrutiva só ao 3Studio e só em estados ativos. A
 * autorização real é em duas camadas (borda do backend + motor do C11).
 */
export default async function ProvaDetalhePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const usuario = await fetchUsuarioAtual();
  const podeCancelar = usuario
    ? can({ setor: usuario.setor, administrador: usuario.administrador }, "cancelar_prova")
    : false;
  // `key={id}`: navegar entre provas REMONTA o view (estado fresco — sem resets
  // síncronos de estado dentro de efeitos; o skeleton reaparece a cada prova).
  return <ProvaDetalheView key={id} provaId={id} podeCancelar={podeCancelar} />;
}
