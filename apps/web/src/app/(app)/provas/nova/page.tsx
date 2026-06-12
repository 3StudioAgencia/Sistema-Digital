import { NovaProvaView } from "./_components/nova-prova-view";

export const dynamic = "force-dynamic";

/**
 * Criação de Prova Digital (W2-C06) — exclusiva do Administrador (Matriz §7,
 * "Criar Prova"): o proxy do C05 já gateia /provas/nova pelo flag admin
 * (recurso criar_prova) e o backend nega 403 em profundidade.
 */
export default function NovaProvaPage() {
  return <NovaProvaView />;
}
