import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { ProvaDetalhe } from "@/lib/api/provas";
import type { AcaoDisponivel } from "@/lib/api/transicoes";

const mocks = vi.hoisted(() => ({
  obterProva: vi.fn(),
  acoesDisponiveis: vi.fn(),
  executarTransicao: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
  // Handle do pad de assinatura (mockado — jsdom não desenha em canvas).
  isEmpty: vi.fn(() => false),
  toDataURL: vi.fn(() => "data:image/png;base64,QUJD"),
  clear: vi.fn(),
  fromDataURL: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace, back: mocks.back }),
}));

vi.mock("@/lib/api/provas", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/provas")>();
  return { ...original, obterProva: mocks.obterProva };
});

vi.mock("@/lib/api/transicoes", () => ({
  acoesDisponiveis: mocks.acoesDisponiveis,
  executarTransicao: mocks.executarTransicao,
}));

// Substitui o react-signature-canvas (canvas real) por um dublê com o handle.
vi.mock("./assinatura-pad", () => ({
  AssinaturaPad: (props: { ref?: { current: unknown } }) => {
    const handle = {
      isEmpty: mocks.isEmpty,
      toDataURL: mocks.toDataURL,
      clear: mocks.clear,
      fromDataURL: mocks.fromDataURL,
    };
    if (typeof props.ref === "function") (props.ref as (h: unknown) => void)(handle);
    else if (props.ref) props.ref.current = handle;
    return <div data-testid="assinatura-pad" />;
  },
}));

import { ConfirmarView } from "./confirmar-view";

const PROVA: ProvaDetalhe = {
  id: "p-1",
  codigo: "PRV-2026-06-A2KMQ9",
  nome: "Mussarela fatiada",
  requerimento: "155295",
  cliente: "Edulat",
  vendedor_id: "v-1",
  vendedor_nome: "Regiane",
  rota: "matriz",
  status: "criada",
  ciclo_atual: 1,
  created_at: "2026-06-16T00:00:00Z",
  finalizada_em: null,
};

const ASSINAR: AcaoDisponivel[] = [
  { acao: "identificar_e_assinar", exige_motivo: false, estado_destino: "retirada_vendedor" },
];
const DECISAO: AcaoDisponivel[] = [
  { acao: "aprovar", exige_motivo: false, estado_destino: "aprovada_vendedor" },
  { acao: "reprovar", exige_motivo: true, estado_destino: "reprovada_vendedor" },
];

function renderView() {
  return render(
    <ToastProvider>
      <ConfirmarView provaId="p-1" />
    </ToastProvider>,
  );
}

beforeEach(() => {
  for (const m of Object.values(mocks)) m.mockReset();
  sessionStorage.clear();
  mocks.obterProva.mockResolvedValue(PROVA);
  mocks.acoesDisponiveis.mockResolvedValue(ASSINAR);
  mocks.executarTransicao.mockResolvedValue({ ...PROVA, status: "retirada_vendedor" });
  mocks.isEmpty.mockReturnValue(false);
  mocks.toDataURL.mockReturnValue("data:image/png;base64,QUJD");
});

describe("ConfirmarView (W3-C12)", () => {
  it("mostra os dados da prova + o pad de assinatura (RF-028: branch autorizado)", async () => {
    renderView();
    expect(
      await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Requerimento: 155295")).toBeInTheDocument();
    expect(screen.getByText("Matriz")).toBeInTheDocument(); // rótulo real da rota
    expect(screen.getByTestId("assinatura-pad")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar" })).toBeInTheDocument();
  });

  it("assinatura + Confirmar → invoca a transição e reflete o novo estado", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("button", { name: "Confirmar" });
    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    await waitFor(() =>
      expect(mocks.executarTransicao).toHaveBeenCalledWith(
        "p-1",
        expect.objectContaining({ acao: "identificar_e_assinar", assinatura: expect.any(String) }),
      ),
    );
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/provas/p-1"));
  });

  it("canvas vazio → bloqueia o envio com aviso (RN-003)", async () => {
    mocks.isEmpty.mockReturnValue(true);
    const user = userEvent.setup();
    renderView();
    await user.click(await screen.findByRole("button", { name: "Confirmar" }));
    expect(await screen.findByText("Desenhe a assinatura para confirmar.")).toBeInTheDocument();
    expect(mocks.executarTransicao).not.toHaveBeenCalled();
  });

  it("não é a vez do ator (lista vazia) → bloqueio genérico, sem pad nem revelar quem é", async () => {
    mocks.acoesDisponiveis.mockResolvedValue([]);
    renderView();
    expect(await screen.findByText(/não está aguardando uma ação sua/i)).toBeInTheDocument();
    expect(screen.queryByTestId("assinatura-pad")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  });

  it("Aprovar/Reprovar; Reprovar exige motivo (RF-008)", async () => {
    mocks.acoesDisponiveis.mockResolvedValue(DECISAO);
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("button", { name: "Aprovar" });
    // Reprovar revela o motivo; sem motivo → bloqueia.
    await user.click(screen.getByRole("button", { name: "Reprovar" }));
    await user.click(screen.getByRole("button", { name: "Confirmar reprovação" }));
    expect(await screen.findByText(/informe o motivo/i)).toBeInTheDocument();
    expect(mocks.executarTransicao).not.toHaveBeenCalled();
    // Com motivo → envia reprovar + motivo.
    await user.type(screen.getByLabelText("Motivo da reprovação"), "cor errada");
    await user.click(screen.getByRole("button", { name: "Confirmar reprovação" }));
    await waitFor(() =>
      expect(mocks.executarTransicao).toHaveBeenCalledWith(
        "p-1",
        expect.objectContaining({ acao: "reprovar", motivo: "cor errada" }),
      ),
    );
  });

  it("Aprovar envia a ação aprovar", async () => {
    mocks.acoesDisponiveis.mockResolvedValue(DECISAO);
    mocks.executarTransicao.mockResolvedValue({ ...PROVA, status: "aprovada_vendedor" });
    const user = userEvent.setup();
    renderView();
    await user.click(await screen.findByRole("button", { name: "Aprovar" }));
    await waitFor(() =>
      expect(mocks.executarTransicao).toHaveBeenCalledWith(
        "p-1",
        expect.objectContaining({ acao: "aprovar" }),
      ),
    );
  });

  it("resiliência: falha de rede preserva o traço e oferece retry com a MESMA chave", async () => {
    mocks.executarTransicao
      .mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "sem rede"))
      .mockResolvedValueOnce({ ...PROVA, status: "retirada_vendedor" });
    const user = userEvent.setup();
    renderView();
    await user.click(await screen.findByRole("button", { name: "Confirmar" }));
    // Falhou: mostra o aviso de preservação + retry; o pad NÃO foi limpo.
    expect(await screen.findByText(/assinatura foi preservada/i)).toBeInTheDocument();
    expect(mocks.clear).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await waitFor(() => expect(mocks.executarTransicao).toHaveBeenCalledTimes(2));
    // A chave de idempotência é a MESMA nas duas tentativas (converge — RNF-015).
    const k1 = mocks.executarTransicao.mock.calls[0][1].idempotencyKey;
    const k2 = mocks.executarTransicao.mock.calls[1][1].idempotencyKey;
    expect(k1).toBe(k2);
  });

  it("404 na carga → toast genérico + volta ao escaneamento (§11)", async () => {
    mocks.obterProva.mockRejectedValue(
      new ApiError(404, "prova_nao_encontrada", "Prova não encontrada."),
    );
    mocks.acoesDisponiveis.mockRejectedValue(
      new ApiError(404, "prova_nao_encontrada", "Prova não encontrada."),
    );
    renderView();
    expect(await screen.findByText("Prova não encontrada.")).toBeInTheDocument();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/escanear"));
  });
});
