import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Timeline } from "@/lib/api/timeline";

const mocks = vi.hoisted(() => ({ obterMovimentacoes: vi.fn() }));

vi.mock("@/lib/api/timeline", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/timeline")>();
  return { ...original, obterMovimentacoes: mocks.obterMovimentacoes };
});

import { ProofTimeline } from "./ProofTimeline";

const FILIAL = ["criada", "encaminhada_para_vendedor", "aprovada_vendedor", "recebida_clicheria"];
const LAM_MATRIZ = [
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
];

function mockMatchMedia(reduce: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: reduce && query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

beforeEach(() => {
  mocks.obterMovimentacoes.mockReset();
  mockMatchMedia(false);
});

describe("ProofTimeline (W3-C13)", () => {
  it("desenha o badge da rota e os estados do caminho (Filial)", async () => {
    mocks.obterMovimentacoes.mockResolvedValue({
      rota: "filial",
      estado_atual: "encaminhada_para_vendedor",
      ciclo_atual: 1,
      criada_em: "2026-04-27T09:00:00Z",
      etapas_canonicas: FILIAL,
      movimentacoes: [
        {
          id: "m1",
          estado_origem: "criada",
          estado_destino: "encaminhada_para_vendedor",
          acao: "identificar_e_assinar",
          ator_id: "v1",
          ator_nome: "Regiane",
          ciclo: 1,
          motivo: null,
          tem_assinatura: true,
          created_at: "2026-04-27T10:01:00Z",
        },
      ],
    } satisfies Timeline);

    render(<ProofTimeline provaId="p-1" />);

    expect(await screen.findByText("Rota: Filial")).toBeInTheDocument();
    expect(screen.getByText("Encaminhada ao vendedor")).toBeInTheDocument();
    expect(screen.getByText("Aprovada")).toBeInTheDocument(); // futura, esmaecida
    expect(screen.getByText("Na clicheria")).toBeInTheDocument();
    expect(screen.getByText(/Regiane/)).toBeInTheDocument(); // responsável
    expect(screen.getByText("✓ Assinada")).toBeInTheDocument(); // selo (DP-2c)
  });

  it("diferencia laminação e travessias de motorista (Lam. Matriz)", async () => {
    mocks.obterMovimentacoes.mockResolvedValue({
      rota: "lam_matriz",
      estado_atual: "criada",
      ciclo_atual: 1,
      criada_em: "2026-04-27T09:00:00Z",
      etapas_canonicas: LAM_MATRIZ,
      movimentacoes: [],
    } satisfies Timeline);

    render(<ProofTimeline provaId="p-1" />);

    expect(await screen.findByText("Rota: Lam. Matriz")).toBeInTheDocument();
    expect(screen.getAllByText("Laminação").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Em trânsito").length).toBeGreaterThan(0);
    // O contexto da travessia está no próprio rótulo do estado.
    expect(screen.getByText("Com motorista — ida laminação")).toBeInTheDocument();
    expect(screen.getByText("Com motorista — entrega final")).toBeInTheDocument();
  });

  it("mostra a reprovação com o motivo em destaque e o responsável cross-setor", async () => {
    mocks.obterMovimentacoes.mockResolvedValue({
      rota: "filial",
      estado_atual: "reprovada_vendedor",
      ciclo_atual: 1,
      criada_em: "2026-04-27T09:00:00Z",
      etapas_canonicas: FILIAL,
      movimentacoes: [
        {
          id: "m1",
          estado_origem: "criada",
          estado_destino: "encaminhada_para_vendedor",
          acao: "identificar_e_assinar",
          ator_id: "s1",
          ator_nome: "Studio Op",
          ciclo: 1,
          motivo: null,
          tem_assinatura: true,
          created_at: "2026-04-27T10:01:00Z",
        },
        {
          id: "m2",
          estado_origem: "encaminhada_para_vendedor",
          estado_destino: "reprovada_vendedor",
          acao: "reprovar",
          ator_id: "v1",
          ator_nome: "Regiane",
          ciclo: 1,
          motivo: "Cor saiu fora do padrão.",
          tem_assinatura: true,
          created_at: "2026-04-27T10:02:00Z",
        },
      ],
    } satisfies Timeline);

    render(<ProofTimeline provaId="p-1" />);

    expect(await screen.findByText("Reprovada")).toBeInTheDocument();
    expect(screen.getByText("Cor saiu fora do padrão.")).toBeInTheDocument();
    expect(screen.getByText(/Studio Op/)).toBeInTheDocument(); // nome cross-setor (DP-2b)
  });

  it("separa múltiplos ciclos com rótulo de ciclo (DP-3)", async () => {
    mocks.obterMovimentacoes.mockResolvedValue({
      rota: "filial",
      estado_atual: "encaminhada_para_vendedor",
      ciclo_atual: 2,
      criada_em: "2026-04-27T09:00:00Z",
      etapas_canonicas: FILIAL,
      movimentacoes: [
        {
          id: "m1",
          estado_origem: "encaminhada_para_vendedor",
          estado_destino: "reprovada_vendedor",
          acao: "reprovar",
          ator_id: "v1",
          ator_nome: "Regiane",
          ciclo: 1,
          motivo: "Refazer.",
          tem_assinatura: true,
          created_at: "2026-04-27T10:02:00Z",
        },
        {
          id: "m2",
          estado_origem: "criada",
          estado_destino: "encaminhada_para_vendedor",
          acao: "identificar_e_assinar",
          ator_id: "v1",
          ator_nome: "Regiane",
          ciclo: 2,
          motivo: null,
          tem_assinatura: true,
          created_at: "2026-04-27T11:00:00Z",
        },
      ],
    } satisfies Timeline);

    render(<ProofTimeline provaId="p-1" />);

    expect(await screen.findByText("Ciclo 1")).toBeInTheDocument();
    expect(screen.getByText("Ciclo 2")).toBeInTheDocument();
  });

  it("falha do histórico mostra erro local com retry — não derruba o detalhe", async () => {
    mocks.obterMovimentacoes.mockRejectedValueOnce(new Error("offline"));
    render(<ProofTimeline provaId="p-1" />);

    expect(await screen.findByText(/não foi possível carregar o histórico/i)).toBeInTheDocument();

    mocks.obterMovimentacoes.mockResolvedValue({
      rota: "filial",
      estado_atual: "criada",
      ciclo_atual: 1,
      criada_em: "2026-04-27T09:00:00Z",
      etapas_canonicas: FILIAL,
      movimentacoes: [],
    } satisfies Timeline);
    await userEvent.setup().click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByText("Rota: Filial")).toBeInTheDocument();
  });

  it("renderiza sob prefers-reduced-motion (revelação instantânea)", async () => {
    mockMatchMedia(true);
    mocks.obterMovimentacoes.mockResolvedValue({
      rota: "filial",
      estado_atual: "criada",
      ciclo_atual: 1,
      criada_em: "2026-04-27T09:00:00Z",
      etapas_canonicas: FILIAL,
      movimentacoes: [],
    } satisfies Timeline);

    render(<ProofTimeline provaId="p-1" />);
    expect(await screen.findByText("Rota: Filial")).toBeInTheDocument();
    expect(screen.getByText("Criada")).toBeInTheDocument();
  });
});
