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
  obterMovimentacoes: vi.fn(),
  cancelarProva: vi.fn(),
  reiniciarCiclo: vi.fn(),
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

// As ações administrativas (Cancelar=C14, Reiniciar=C15) chamam endpoints
// dedicados; mockadas para isolar a UI.
vi.mock("@/lib/api/transicoes", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/transicoes")>();
  return {
    ...original,
    cancelarProva: mocks.cancelarProva,
    reiniciarCiclo: mocks.reiniciarCiclo,
  };
});

// A timeline (C13) faz seu próprio fetch; mockado aqui para isolar o detalhe.
vi.mock("@/lib/api/timeline", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/timeline")>();
  return { ...original, obterMovimentacoes: mocks.obterMovimentacoes };
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

function renderView(opts?: { podeCancelar?: boolean; podeReiniciar?: boolean }) {
  return render(
    <ToastProvider>
      <ProvaDetalheView
        provaId="p-1"
        podeCancelar={opts?.podeCancelar ?? false}
        podeReiniciar={opts?.podeReiniciar ?? false}
      />
    </ToastProvider>,
  );
}

beforeEach(() => {
  for (const m of Object.values(mocks)) m.mockReset();
  mocks.obterProva.mockResolvedValue(PROVA);
  mocks.cancelarProva.mockResolvedValue({
    ...PROVA,
    status: "cancelada",
    finalizada_em: "2026-06-17T12:00:00Z",
  });
  // Reinício devolve a prova já em "Criada" no novo ciclo (status + ciclo_atual).
  mocks.reiniciarCiclo.mockResolvedValue({ ...PROVA, status: "criada", ciclo_atual: 2 });
  mocks.baixarArte.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" }));
  mocks.baixarEtiqueta.mockResolvedValue(
    new Blob([new Uint8Array([4, 5, 6])], { type: "application/pdf" }),
  );
  mocks.obterMovimentacoes.mockResolvedValue({
    rota: "lam_matriz",
    estado_atual: "criada",
    ciclo_atual: 1,
    criada_em: "2026-04-27T00:00:00Z",
    etapas_canonicas: [
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
    movimentacoes: [],
  });
  // jsdom não implementa object URLs — stub determinístico.
  let n = 0;
  global.URL.createObjectURL = vi.fn(() => `blob:mock-${++n}`);
  global.URL.revokeObjectURL = vi.fn();
  // crypto.randomUUID (chave de idempotência do modal de cancelar) — garante o env.
  if (typeof globalThis.crypto?.randomUUID !== "function") {
    Object.defineProperty(globalThis, "crypto", {
      value: { ...globalThis.crypto, randomUUID: () => "11111111-1111-1111-1111-111111111111" },
      configurable: true,
    });
  }
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

  it("histórico pluga a timeline visual (W3-C13) com o esqueleto da rota", async () => {
    renderView();
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });
    // A ProofTimeline busca o próprio histórico e desenha o badge da rota no topo.
    expect(await screen.findByText("Rota: Lam. Matriz")).toBeInTheDocument();
    expect(mocks.obterMovimentacoes).toHaveBeenCalledWith("p-1", expect.anything());
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

describe("Cancelamento de prova (W3-C14)", () => {
  it("não oferece 'Cancelar prova' a quem não pode (não-3Studio)", async () => {
    renderView({ podeCancelar: false });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });
    expect(screen.queryByRole("button", { name: "Cancelar prova" })).not.toBeInTheDocument();
  });

  it("não oferece 'Cancelar prova' em estado terminal, mesmo ao 3Studio (irreversível)", async () => {
    mocks.obterProva.mockResolvedValue({ ...PROVA, status: "recebida_clicheria" });
    renderView({ podeCancelar: true });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });
    expect(screen.queryByRole("button", { name: "Cancelar prova" })).not.toBeInTheDocument();
  });

  it("3Studio em estado ativo: abre o modal, exige motivo e cancela refletindo 'Cancelada'", async () => {
    const user = userEvent.setup();
    renderView({ podeCancelar: true });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });

    // Abre o modal destrutivo a partir do detalhe.
    await user.click(screen.getByRole("button", { name: "Cancelar prova" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/irreversível/i)).toBeInTheDocument(); // aviso RN-005

    // Sem motivo, o confirmar está BLOQUEADO (desabilitado) — nada é enviado.
    const confirmar = within(dialog).getByRole("button", { name: "Cancelar prova" });
    expect(confirmar).toBeDisabled();
    expect(mocks.cancelarProva).not.toHaveBeenCalled();

    // Com motivo, confirma → o motor é invocado (endpoint dedicado).
    await user.type(within(dialog).getByLabelText(/Motivo/i), "cliente desistiu");
    expect(confirmar).toBeEnabled();
    await user.click(confirmar);

    await waitFor(() =>
      expect(mocks.cancelarProva).toHaveBeenCalledWith("p-1", {
        motivo: "cliente desistiu",
        idempotencyKey: expect.any(String),
      }),
    );
    // Sucesso: toast + estado reflete "Cancelada" e a ação some (terminal).
    expect(await screen.findByText("Prova cancelada.")).toBeInTheDocument();
    const statusRotulo = await screen.findByText("Status:");
    await waitFor(() =>
      expect(
        within(statusRotulo.closest("div") as HTMLElement).getByText("Cancelada"),
      ).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Cancelar prova" })).not.toBeInTheDocument(),
    );
    // A timeline recarrega para mostrar a nova movimentação (recarregar bumpado).
    await waitFor(() => expect(mocks.obterMovimentacoes.mock.calls.length).toBeGreaterThan(1));
  });

  it("erro de regra (já terminal) vira toast e fecha sem alterar o detalhe", async () => {
    const user = userEvent.setup();
    mocks.cancelarProva.mockRejectedValue(
      new ApiError(
        422,
        "transicao_invalida",
        "Esta ação não é válida para a prova no estado atual.",
      ),
    );
    renderView({ podeCancelar: true });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });

    await user.click(screen.getByRole("button", { name: "Cancelar prova" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/Motivo/i), "tentativa tardia");
    await user.click(within(dialog).getByRole("button", { name: "Cancelar prova" }));

    expect(await screen.findByText(/não é válida para a prova/i)).toBeInTheDocument(); // toast da regra
    expect(mocks.replace).not.toHaveBeenCalled(); // 422 não redireciona (≠ 404)
  });
});

describe("Reinício de ciclo (W3-C15)", () => {
  const REPROVADA: ProvaDetalhe = { ...PROVA, status: "reprovada_vendedor" };

  it("não oferece 'Reiniciar ciclo' a quem não pode (não-3Studio)", async () => {
    mocks.obterProva.mockResolvedValue(REPROVADA);
    renderView({ podeReiniciar: false });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });
    expect(screen.queryByRole("button", { name: "Reiniciar ciclo" })).not.toBeInTheDocument();
  });

  it("não oferece 'Reiniciar ciclo' fora de 'Reprovada pelo Vendedor', mesmo ao 3Studio", async () => {
    // PROVA padrão está em 'encaminhada_para_vendedor' (≠ reprovada): botão ausente.
    renderView({ podeReiniciar: true });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });
    expect(screen.queryByRole("button", { name: "Reiniciar ciclo" })).not.toBeInTheDocument();
  });

  it("3Studio em 'Reprovada pelo Vendedor': abre o modal (sem motivo), reinicia e reflete 'Criada' + ciclo 2", async () => {
    const user = userEvent.setup();
    mocks.obterProva.mockResolvedValue(REPROVADA);
    renderView({ podeReiniciar: true });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });

    // Abre o modal de confirmação a partir do detalhe.
    await user.click(screen.getByRole("button", { name: "Reiniciar ciclo" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/novo ciclo/i)).toBeInTheDocument(); // explica o reinício
    expect(within(dialog).getByText(/histórico do ciclo anterior é preservado/i)).toBeInTheDocument();
    // NÃO há campo de motivo (≠ cancelar — DP-2).
    expect(within(dialog).queryByLabelText(/Motivo/i)).not.toBeInTheDocument();

    // Confirma → o motor é invocado (endpoint dedicado), só com a chave de idempotência.
    await user.click(within(dialog).getByRole("button", { name: "Reiniciar ciclo" }));
    await waitFor(() =>
      expect(mocks.reiniciarCiclo).toHaveBeenCalledWith("p-1", {
        idempotencyKey: expect.any(String),
      }),
    );

    // Sucesso: toast + estado reflete "Criada" e o ciclo incrementado (2); a ação some.
    expect(await screen.findByText("Ciclo reiniciado.")).toBeInTheDocument();
    const statusRotulo = await screen.findByText("Status:");
    await waitFor(() =>
      expect(
        within(statusRotulo.closest("div") as HTMLElement).getByText("Criada"),
      ).toBeInTheDocument(),
    );
    const cicloRotulo = screen.getByText("Ciclo Atual:");
    expect(within(cicloRotulo.closest("div") as HTMLElement).getByText("2")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Reiniciar ciclo" })).not.toBeInTheDocument(),
    );
    // A timeline recarrega para mostrar o novo ciclo separado (recarregar bumpado).
    await waitFor(() => expect(mocks.obterMovimentacoes.mock.calls.length).toBeGreaterThan(1));
  });

  it("erro de regra (já não reprovada) vira toast e fecha sem alterar o detalhe", async () => {
    const user = userEvent.setup();
    mocks.obterProva.mockResolvedValue(REPROVADA);
    mocks.reiniciarCiclo.mockRejectedValue(
      new ApiError(422, "transicao_invalida", "Esta ação não é válida para a prova no estado atual."),
    );
    renderView({ podeReiniciar: true });
    await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 });

    await user.click(screen.getByRole("button", { name: "Reiniciar ciclo" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Reiniciar ciclo" }));

    expect(await screen.findByText(/não é válida para a prova/i)).toBeInTheDocument(); // toast da regra
    expect(mocks.replace).not.toHaveBeenCalled(); // 422 não redireciona (≠ 404)
  });
});
