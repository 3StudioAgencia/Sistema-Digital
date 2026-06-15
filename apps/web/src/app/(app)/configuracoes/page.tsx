import { ConfiguracoesView } from "./_components/configuracoes-view";

/**
 * Configurações do sistema (W2-C09) — exclusiva do 3Studio (Matriz §7).
 *
 * Server component fino: o proxy (C05) já gateia a rota pelo flag administrador;
 * o view (client) busca via `apiFetch` e, em profundidade, o backend nega 403 a
 * não-admin (estado "restrito"). Settings reais do RF-022 (DP-6): tempo de atraso
 * (RN-008) e template de etiqueta (RN-011/DP-5), com "Salvar" por card.
 */
export default function ConfiguracoesPage() {
  return <ConfiguracoesView />;
}
