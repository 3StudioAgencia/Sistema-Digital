import type { Movimentacao, Timeline } from "@/lib/api/timeline";
import type { EstadoProva } from "@/lib/provas/status-labels";

export const ESTADOS_LAMINACAO: ReadonlySet<EstadoProva> = new Set<EstadoProva>([
  "encaminhada_para_laminacao",
  "com_motorista_ida_laminacao",
  "laminacao_concluida",
  "com_motorista_volta_laminacao",
  "de_volta_studio_pos_laminacao",
]);

export const ESTADOS_MOTORISTA: ReadonlySet<EstadoProva> = new Set<EstadoProva>([
  "com_motorista_ida_laminacao",
  "com_motorista_volta_laminacao",
  "com_motorista_entrega_final",
]);

const ACOES_AVANCO = new Set(["identificar_e_assinar", "aprovar"]);

export type StatusEtapa = "percorrido" | "atual" | "futuro" | "nao_percorrido";

export type EtapaNode = {
  tipo: "etapa";
  estado: EstadoProva;
  status: StatusEtapa;
  laminacao: boolean;
  motorista: boolean;
  ator_nome: string | null;
  quando: string | null;
  tem_assinatura: boolean;
};

export type EventoNode = {
  tipo: "reprovacao" | "cancelamento" | "reinicio";
  acao: Movimentacao["acao"];
  ator_nome: string | null;
  quando: string | null;
  motivo: string | null;
  atual: boolean;
};

export type TimelineNode = EtapaNode | EventoNode;

export type CicloTimeline = {
  numero: number;
  nodes: TimelineNode[];
};

export type TimelineRender = {
  ciclos: CicloTimeline[];
};

function etapaNode(
  estado: EstadoProva,
  mov: Movimentacao | undefined,
  estadoAtual: EstadoProva,
  isCurrent: boolean,
  criadaEm: string | null,
): EtapaNode {
  let status: StatusEtapa;
  if (isCurrent && estado === estadoAtual) status = "atual";
  else if (mov) status = "percorrido";
  else if (estado === "criada")
    status = "percorrido"; // a prova sempre nasce criada
  else if (isCurrent) status = "futuro";
  else status = "nao_percorrido"; // ciclo passado que não chegou aqui (reprovado antes)

  return {
    tipo: "etapa",
    estado,
    status,
    laminacao: ESTADOS_LAMINACAO.has(estado),
    motorista: ESTADOS_MOTORISTA.has(estado),
    ator_nome: mov?.ator_nome ?? null,
    quando: mov?.created_at ?? (estado === "criada" ? criadaEm : null),
    tem_assinatura: mov?.tem_assinatura ?? false,
  };
}

function eventoNode(m: Movimentacao, estadoAtual: EstadoProva, isCurrent: boolean): EventoNode {
  const tipo: EventoNode["tipo"] =
    m.acao === "cancelar" ? "cancelamento" : m.acao === "reprovar" ? "reprovacao" : "reinicio";
  const atual =
    isCurrent &&
    ((m.acao === "reprovar" && estadoAtual === "reprovada_vendedor") ||
      (m.acao === "cancelar" && estadoAtual === "cancelada"));
  return {
    tipo,
    acao: m.acao,
    ator_nome: m.ator_nome,
    quando: m.created_at,
    motivo: m.motivo,
    atual,
  };
}

function construirCiclo(t: Timeline, ciclo: number): TimelineNode[] {
  const isCurrent = ciclo === t.ciclo_atual;
  const movs = t.movimentacoes.filter((m) => m.ciclo === ciclo);

  const reachedByState = new Map<EstadoProva, Movimentacao>();
  for (const m of movs) {
    if (ACOES_AVANCO.has(m.acao)) reachedByState.set(m.estado_destino, m);
  }

  const ultimoIndice = Math.max(0, t.etapas_canonicas.length - 1);
  const eventosPorIndice = new Map<number, Movimentacao[]>();
  for (const m of movs) {
    if (ACOES_AVANCO.has(m.acao)) continue;
    const idx = t.etapas_canonicas.indexOf(m.estado_origem);
    const chave = idx === -1 ? ultimoIndice : idx;
    const lista = eventosPorIndice.get(chave) ?? [];
    lista.push(m);
    eventosPorIndice.set(chave, lista);
  }

  const criadaEm = ciclo === 1 ? t.criada_em : null;
  const nodes: TimelineNode[] = [];
  t.etapas_canonicas.forEach((estado, i) => {
    nodes.push(etapaNode(estado, reachedByState.get(estado), t.estado_atual, isCurrent, criadaEm));
    for (const m of eventosPorIndice.get(i) ?? []) {
      nodes.push(eventoNode(m, t.estado_atual, isCurrent));
    }
  });
  return nodes;
}

export function construirTimeline(t: Timeline): TimelineRender {
  const presentes = new Set<number>(t.movimentacoes.map((m) => m.ciclo));
  presentes.add(t.ciclo_atual);
  const ciclos = [...presentes].sort((a, b) => a - b);
  return { ciclos: ciclos.map((numero) => ({ numero, nodes: construirCiclo(t, numero) })) };
}
