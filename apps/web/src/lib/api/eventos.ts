/**
 * Stream SSE do dashboard (etapa 3 da migração Supabase->local — substitui o
 * Realtime do Supabase).
 *
 * Abre um `EventSource` na MESMA ORIGEM (`/api/dashboard/stream`, rewrite do
 * next.config): o cookie httpOnly de sessão flui automaticamente — o `EventSource`
 * não aceita header custom (nem `Authorization`), então o cookie same-origin é o
 * único caminho de auth possível, e é justamente o que o rewrite entrega.
 *
 * O evento é GENÉRICO ("mudou"): `onMudou` deve rebuscar `GET /dashboard` (que já
 * vem escopado pela RLS por perfil) — nada sensível trafega no canal. O servidor
 * fecha o stream pouco antes de o access token expirar, emitindo o evento `expira`;
 * o chamador deve então renovar o cookie (`POST /api/auth/refresh`) e reabrir — o
 * `EventSource` nativo não faz refresh sozinho.
 *
 * Devolve um cleanup que fecha o `EventSource` (chamar no unmount / ao reabrir).
 */

export type OpcoesStreamDashboard = {
  /** Chegou um sinal "algo mudou" — rebusque a agregação (com debounce). Também
   *  disparado no `conectado` inicial, para reconciliar assim que (re)conecta. */
  onMudou: () => void;
  /** O servidor pediu reconexão (token perto de expirar) — renove e reabra. */
  onExpira: () => void;
};

const STREAM_URL = "/api/dashboard/stream";

export function assinarDashboard({ onMudou, onExpira }: OpcoesStreamDashboard): () => void {
  // Ambiente sem EventSource (SSR / teste sem stub): degrada para no-op — o
  // dashboard segue na carga SSR + refetch manual, sem quebrar.
  if (typeof EventSource === "undefined") return () => {};

  const es = new EventSource(STREAM_URL, { withCredentials: true });
  // "data: mudou" chega como message padrão (sem campo `event:`). O heartbeat
  // (`: ping`) é comentário SSE e é ignorado pelo EventSource (não dispara nada).
  es.onmessage = () => onMudou();
  es.addEventListener("conectado", () => onMudou());
  es.addEventListener("expira", () => onExpira());
  return () => es.close();
}
