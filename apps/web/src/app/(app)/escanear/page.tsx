import { EscanearView } from "./_components/escanear-view";

/**
 * Escanear prova (W3-C10) — primeira tela da Wave 3 e a mais mobile-first do
 * sistema (operadores no celular, em pé, sob luz forte — RF-029/US-020).
 *
 * Server component fino: delega ao client view, que faz a leitura por câmera
 * (in-app, com degradação graciosa) e a digitação manual (máscara do formato do
 * C06), ambas resolvendo a prova por `POST /provas/identificar`. A rota é o
 * recurso universal `escanear` na Matriz §7; o ESCOPO é da RLS, no servidor.
 */
export default function EscanearPage() {
  return <EscanearView />;
}
