import { describe, expect, it } from "vitest";

import type { Movimentacao, Timeline } from "@/lib/api/timeline";
import type { EstadoProva } from "@/lib/provas/status-labels";

import { construirTimeline, type EtapaNode, type EventoNode, type TimelineNode } from "./timeline";

// Esqueletos canônicos por rota (espelham `sequencia_canonica` do backend — DP-1).
const CANONICAS: Record<Timeline["rota"], EstadoProva[]> = {
  matriz: [
    "criada",
    "retirada_vendedor",
    "aprovada_vendedor",
    "de_volta_studio",
    "com_motorista_entrega_final",
    "recebida_clicheria",
  ],
  lam_matriz: [
    "criada",
    "encaminhada_para_laminacao",
    "com_motorista_ida_laminacao",
    "laminacao_concluida",
    "com_motorista_volta_laminacao",
    "de_volta_studio_pos_laminacao",
    "retirada_vendedor",
    "aprovada_vendedor",
    "de_volta_studio",
    "com_motorista_entrega_final",
    "recebida_clicheria",
  ],
  filial: ["criada", "encaminhada_para_vendedor", "aprovada_vendedor", "recebida_clicheria"],
  lam_filial: [
    "criada",
    "encaminhada_para_laminacao",
    "com_motorista_ida_laminacao",
    "laminacao_concluida",
    "encaminhada_para_vendedor",
    "aprovada_vendedor",
    "recebida_clicheria",
  ],
};

let seq = 0;
function mov(
  p: Partial<Movimentacao> & Pick<Movimentacao, "estado_origem" | "estado_destino" | "acao">,
): Movimentacao {
  seq += 1;
  return {
    id: `m-${seq}`,
    ator_id: "a-1",
    ator_nome: "Regiane",
    ciclo: 1,
    motivo: null,
    tem_assinatura: true,
    created_at: `2026-04-27T10:0${seq}:00Z`,
    ...p,
  };
}

function timeline(over: Partial<Timeline> & Pick<Timeline, "rota" | "estado_atual">): Timeline {
  return {
    ciclo_atual: 1,
    criada_em: "2026-04-27T09:00:00Z",
    etapas_canonicas: CANONICAS[over.rota],
    movimentacoes: [],
    ...over,
  };
}

function etapas(nodes: TimelineNode[]): EtapaNode[] {
  return nodes.filter((n): n is EtapaNode => n.tipo === "etapa");
}

describe("construirTimeline (W3-C13)", () => {
  it("renderiza o esqueleto das 4 rotas com o número correto de etapas", () => {
    const tamanhos: Record<Timeline["rota"], number> = {
      matriz: 6,
      lam_matriz: 11,
      filial: 4,
      lam_filial: 7,
    };
    for (const rota of Object.keys(tamanhos) as Timeline["rota"][]) {
      const r = construirTimeline(timeline({ rota, estado_atual: "criada" }));
      expect(r.ciclos).toHaveLength(1);
      expect(etapas(r.ciclos[0].nodes)).toHaveLength(tamanhos[rota]);
    }
  });

  it("sem histórico: CRIADA é a atual e o resto futuro, com a data de criação", () => {
    const r = construirTimeline(timeline({ rota: "filial", estado_atual: "criada" }));
    const es = etapas(r.ciclos[0].nodes);
    expect(es[0]).toMatchObject({
      estado: "criada",
      status: "atual",
      quando: "2026-04-27T09:00:00Z",
    });
    expect(es.slice(1).every((e) => e.status === "futuro")).toBe(true);
  });

  it("marca percorrida/atual/futura conforme as movimentações (Matriz)", () => {
    const r = construirTimeline(
      timeline({
        rota: "matriz",
        estado_atual: "aprovada_vendedor",
        movimentacoes: [
          mov({
            estado_origem: "criada",
            estado_destino: "retirada_vendedor",
            acao: "identificar_e_assinar",
          }),
          mov({
            estado_origem: "retirada_vendedor",
            estado_destino: "aprovada_vendedor",
            acao: "aprovar",
          }),
        ],
      }),
    );
    const es = etapas(r.ciclos[0].nodes);
    expect(es.map((e) => e.status)).toEqual([
      "percorrido", // criada
      "percorrido", // retirada_vendedor
      "atual", // aprovada_vendedor
      "futuro", // de_volta_studio
      "futuro", // com_motorista_entrega_final
      "futuro", // recebida_clicheria
    ]);
    // Responsável + selo de assinatura nas etapas percorridas.
    expect(es[1]).toMatchObject({ ator_nome: "Regiane", tem_assinatura: true });
    expect(es[1].quando).toBeTruthy();
  });

  it("diferencia laminação e contexto de motorista (Lam. Matriz)", () => {
    const r = construirTimeline(timeline({ rota: "lam_matriz", estado_atual: "criada" }));
    const porEstado = new Map(etapas(r.ciclos[0].nodes).map((e) => [e.estado, e]));
    expect(porEstado.get("encaminhada_para_laminacao")).toMatchObject({
      laminacao: true,
      motorista: false,
    });
    expect(porEstado.get("com_motorista_ida_laminacao")).toMatchObject({
      laminacao: true,
      motorista: true,
    });
    expect(porEstado.get("com_motorista_entrega_final")).toMatchObject({
      laminacao: false,
      motorista: true,
    });
    expect(porEstado.get("retirada_vendedor")).toMatchObject({
      laminacao: false,
      motorista: false,
    });
  });

  it("reprovação vira evento com motivo, destacado e após a etapa de decisão (Filial)", () => {
    const r = construirTimeline(
      timeline({
        rota: "filial",
        estado_atual: "reprovada_vendedor",
        movimentacoes: [
          mov({
            estado_origem: "criada",
            estado_destino: "encaminhada_para_vendedor",
            acao: "identificar_e_assinar",
          }),
          mov({
            estado_origem: "encaminhada_para_vendedor",
            estado_destino: "reprovada_vendedor",
            acao: "reprovar",
            motivo: "Cor fora do padrão.",
            tem_assinatura: true,
          }),
        ],
      }),
    );
    const nodes = r.ciclos[0].nodes;
    const idxDecisao = nodes.findIndex(
      (n) => n.tipo === "etapa" && n.estado === "encaminhada_para_vendedor",
    );
    const idxReprov = nodes.findIndex((n) => n.tipo === "reprovacao");
    expect(idxReprov).toBe(idxDecisao + 1); // logo após a etapa de decisão
    const reprov = nodes[idxReprov] as EventoNode;
    expect(reprov).toMatchObject({
      tipo: "reprovacao",
      motivo: "Cor fora do padrão.",
      atual: true,
    });
  });

  it("cancelamento vira evento terminal destacado com motivo", () => {
    const r = construirTimeline(
      timeline({
        rota: "matriz",
        estado_atual: "cancelada",
        movimentacoes: [
          mov({
            estado_origem: "criada",
            estado_destino: "retirada_vendedor",
            acao: "identificar_e_assinar",
          }),
          mov({
            estado_origem: "retirada_vendedor",
            estado_destino: "cancelada",
            acao: "cancelar",
            motivo: "Pedido cancelado pelo cliente.",
          }),
        ],
      }),
    );
    const cancel = r.ciclos[0].nodes.find((n) => n.tipo === "cancelamento") as EventoNode;
    expect(cancel).toMatchObject({
      tipo: "cancelamento",
      motivo: "Pedido cancelado pelo cliente.",
      atual: true,
    });
  });

  it("agrupa múltiplos ciclos com separação por número de ciclo (DP-3)", () => {
    const r = construirTimeline(
      timeline({
        rota: "filial",
        estado_atual: "aprovada_vendedor",
        ciclo_atual: 2,
        movimentacoes: [
          mov({
            estado_origem: "criada",
            estado_destino: "encaminhada_para_vendedor",
            acao: "identificar_e_assinar",
            ciclo: 1,
          }),
          mov({
            estado_origem: "encaminhada_para_vendedor",
            estado_destino: "reprovada_vendedor",
            acao: "reprovar",
            motivo: "Refazer.",
            ciclo: 1,
          }),
          mov({
            estado_origem: "reprovada_vendedor",
            estado_destino: "criada",
            acao: "reiniciar_ciclo",
            ciclo: 1,
          }),
          mov({
            estado_origem: "criada",
            estado_destino: "encaminhada_para_vendedor",
            acao: "identificar_e_assinar",
            ciclo: 2,
          }),
          mov({
            estado_origem: "encaminhada_para_vendedor",
            estado_destino: "aprovada_vendedor",
            acao: "aprovar",
            ciclo: 2,
          }),
        ],
      }),
    );
    expect(r.ciclos.map((c) => c.numero)).toEqual([1, 2]);
    // Ciclo 1 (passado): reprovação presente; aprovada nunca alcançada (não percorrida).
    const c1 = r.ciclos[0].nodes;
    expect(c1.some((n) => n.tipo === "reprovacao")).toBe(true);
    const aprovadaC1 = etapas(c1).find((e) => e.estado === "aprovada_vendedor");
    expect(aprovadaC1?.status).toBe("nao_percorrido");
    // Ciclo 2 (atual): aprovada é a atual.
    const aprovadaC2 = etapas(r.ciclos[1].nodes).find((e) => e.estado === "aprovada_vendedor");
    expect(aprovadaC2?.status).toBe("atual");
  });
});
