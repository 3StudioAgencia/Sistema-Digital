import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { ProvaDetalhe } from "@/lib/api/provas";

const mocks = vi.hoisted(() => ({
  obterProva: vi.fn(),
  baixarArte: vi.fn(),
  baixarEtiqueta: vi.fn(),
  salvarArquivo: vi.fn(),
  back: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: mocks.back, push: mocks.push, replace: mocks.replace }),
}));

vi.mock("@/lib/api/provas", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/provas")>();
  return {
    ...original,
    obterProva: mocks.obterProva,
    baixarArte: mocks.baixarArte,
    baixarEtiqueta: mocks.baixarEtiqueta,
    salvarArquivo: mocks.salvarArquivo,
  };
});

import { ProvaDetalheView } from "./prova-detalhe-view";

const PROVA: ProvaDetalhe = {
  id: "p-1",
  codigo: "PRV-2026-04-K3T9XB",
  nome: "Mussarela fatiada",
  requerimento: "123456",
  cliente: "Edulat",
  vendedor_id: "v-1",
  vendedor_nome: "Regiane",
  rota: "lam_matriz",
  status: "encaminhada_para_vendedor",
  ciclo_atual: 1,
  created_at: "2026-04-27T00:00:00Z",
  finalizada_em: null,
};

function renderView() {
  return render(
    <ToastProvider>
      <ProvaDetalheView provaId="p-1" />
    </ToastProvider>,
  );
}

beforeEach(() => {
  for (const m of Object.values(mocks)) m.mockReset();
  mocks.obterProva.mockResolvedValue(PROVA);
  mocks.baixarArte.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" }));
  mocks.baixarEtiqueta.mockResolvedValue(
    new Blob([new Uint8Array([4, 5, 6])], { type: "application/pdf" }),
  );
  // jsdom não implementa object URLs — stub determinístico.
  let n = 0;
  global.URL.createObjectURL = vi.fn(() => `blob:mock-${++n}`);
  global.URL.revokeObjectURL = vi.fn();
  // history.length é 1 no jsdom (entrada direta) por padrão.
});

describe("ProvaDetalheView (W2-C08)", () => {
  it("renderiza o detalhe fiel ao design: metadados, rótulos de rota/status e ações", async () => {
    renderView();

    expect(
      await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Requerimento: 123456")).toBeInTheDocument();
    expect(screen.getByText("Edulat")).toBeInTheDocument();
    expect(screen.getByText("Regiane")).toBeInTheDocument();
    expect(screen.getByText("Lam. Matriz")).toBeInTheDocument(); // rótulo da rota (DP-7)
    expect(screen.getByText("Encaminhada ao vendedor")).toBeInTheDocument(); // rótulo do status (C07)
    expect(screen.getByText("27/04/2026")).toBeInTheDocument(); // data formatada
    // Ciclo Atual (DP-1)
    const cicloRotulo = screen.getByText("Ciclo Atual:");
    expect(within(cicloRotulo.closest("div") as HTMLElement).getByText("1")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Visualizar etiqueta" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Baixar etiqueta" })).toBeInTheDocument();
  });

  it("histórico nasce em empty state (DP-2 — fronteira com C11/C13)", async () => {
    renderView();
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });
    expect(screen.getByText("Esta prova ainda não teve movimentações.")).toBeInTheDocument();
    expect(
      screen.getByText(/timeline visual fica disponível quando a prova for escaneada/i),
    ).toBeInTheDocument();
  });

  it("exibe a arte vinda do proxy do backend (DP-5: blob → objectURL, sem URL pública)", async () => {
    renderView();
    const img = (await screen.findByAltText(/Arte da prova Mussarela fatiada/)) as HTMLImageElement;
    expect(mocks.baixarArte).toHaveBeenCalledWith("p-1", expect.anything());
    expect(img.getAttribute("src")).toMatch(/^blob:mock-/); // nunca uma URL do R2
  });

  it("404 (inexistente OU fora do escopo) → toast genérico + volta à listagem (anti-enumeração)", async () => {
    mocks.obterProva.mockRejectedValue(
      new ApiError(404, "prova_nao_encontrada", "Prova não encontrada."),
    );
    renderView();

    expect(await screen.findByText("Prova não encontrada.")).toBeInTheDocument(); // toast
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/provas"));
  });

  it("'Baixar etiqueta' baixa o PDF do C06 com o nome do arquivo pelo código", async () => {
    const user = userEvent.setup();
    renderView();
    await user.click(await screen.findByRole("button", { name: "Baixar etiqueta" }));

    await waitFor(() => expect(mocks.baixarEtiqueta).toHaveBeenCalledWith("p-1"));
    expect(mocks.salvarArquivo).toHaveBeenCalledWith(
      expect.any(Blob),
      "etiqueta-PRV-2026-04-K3T9XB.pdf",
    );
  });

  it("'Visualizar etiqueta' abre o preview em modal (DP-4)", async () => {
    const user = userEvent.setup();
    renderView();
    await user.click(await screen.findByRole("button", { name: "Visualizar etiqueta" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Etiqueta — PRV-2026-04-K3T9XB/)).toBeInTheDocument();
    expect(within(dialog).getByTitle(/Etiqueta da prova PRV-2026-04-K3T9XB/)).toBeInTheDocument();
  });

  it("revoga o objectURL da etiqueta ao desmontar com o modal aberto (sem vazar blob)", async () => {
    const user = userEvent.setup();
    const { unmount } = renderView();
    await user.click(await screen.findByRole("button", { name: "Visualizar etiqueta" }));
    await screen.findByRole("dialog");

    unmount(); // sai por sidebar/back/troca de prova sem passar por "Fechar"
    expect(URL.revokeObjectURL).toHaveBeenCalledWith(expect.stringMatching(/^blob:mock-/));
  });

  it("'Voltar' sem histórico cai na listagem (fallback do DP-6)", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });

    await user.click(screen.getByRole("button", { name: /Voltar/ }));
    expect(mocks.push).toHaveBeenCalledWith("/provas"); // jsdom: history.length === 1
  });

  it("erro não-404 mostra estado de erro com retry", async () => {
    mocks.obterProva.mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "API fora."));
    renderView();
    expect(await screen.findByText(/não foi possível carregar a prova/i)).toBeInTheDocument();

    mocks.obterProva.mockResolvedValue(PROVA);
    await userEvent.setup().click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(
      await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 }),
    ).toBeInTheDocument();
  });
});
