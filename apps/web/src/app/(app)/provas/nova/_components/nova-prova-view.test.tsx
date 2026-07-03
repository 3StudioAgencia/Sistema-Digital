import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { Prova, RequerimentoResolvido } from "@/lib/api/provas";

const mocks = vi.hoisted(() => ({
  consultarRequerimento: vi.fn(),
  baixarArteRequerimento: vi.fn(),
  criarProva: vi.fn(),
  baixarEtiqueta: vi.fn(),
  salvarArquivo: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/api/provas", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/provas")>();
  return {
    ...original,
    consultarRequerimento: mocks.consultarRequerimento,
    baixarArteRequerimento: mocks.baixarArteRequerimento,
    criarProva: mocks.criarProva,
    baixarEtiqueta: mocks.baixarEtiqueta,
    salvarArquivo: mocks.salvarArquivo,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

import { NovaProvaView } from "./nova-prova-view";

const REQ: RequerimentoResolvido = {
  cod_req_art: 150288,
  nome: "Queijo Mussarela Flora Milk",
  cod_cliente: 1058,
  nome_cliente: "Laticinios Florida Ltda",
  cod_vendedor: 10,
  nome_vendedor: "Regislaine Petrim",
  cod_vend_fat: 10,
  anexo_imagem: "VERSAO_150288_V3.jpg",
};

const PROVA: Prova = {
  id: "p-1",
  codigo: "PRV-2026-06-K3T9XB",
  nome: "Queijo Mussarela Flora Milk",
  requerimento: "150288",
  cliente: "Laticinios Florida Ltda",
  vendedor_id: "v-1",
  rota: "matriz",
  status: "criada",
  created_at: "2026-06-12T00:00:00Z",
};

function renderView() {
  return render(
    <ToastProvider>
      <NovaProvaView />
    </ToastProvider>,
  );
}

async function resolverRequerimento(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Requerimento:"), "150288");
  // debounce (350 ms) + fetch mockado → auto-preenche travado
  expect(
    await screen.findByText("✓ Requerimento encontrado.", undefined, { timeout: 2000 }),
  ).toBeInTheDocument();
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.consultarRequerimento.mockResolvedValue(REQ);
  mocks.baixarArteRequerimento.mockResolvedValue(
    new Blob([new Uint8Array([0xff, 0xd8, 0xff])], { type: "image/jpeg" }),
  );
  mocks.criarProva.mockResolvedValue(PROVA);
  mocks.baixarEtiqueta.mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
  // jsdom não implementa object URLs — stub determinístico.
  let n = 0;
  global.URL.createObjectURL = vi.fn(() => `blob:mock-${++n}`);
  global.URL.revokeObjectURL = vi.fn();
});

describe("NovaProvaView (Fatia 4 — criação por requerimento)", () => {
  it("renderiza: título, botão, requerimento, rota (4 opções) e SEM upload de arte", () => {
    renderView();

    expect(screen.getByRole("heading", { name: "Nova prova Digital" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar Prova" })).toBeInTheDocument();
    expect(screen.getByLabelText("Requerimento:")).toBeInTheDocument();
    const opcoes = screen.getAllByRole("radio");
    expect(opcoes.map((o) => o.textContent)).toEqual([
      "Matriz",
      "Filial",
      "Lam. Matriz",
      "Lam. Filial",
    ]);
    // o upload manual saiu (Fatia 4)
    expect(screen.queryByText("Solte ou clique")).not.toBeInTheDocument();
  });

  it("digitar o requerimento resolve no ERP e auto-preenche os campos travados", async () => {
    const user = userEvent.setup();
    renderView();

    await user.type(screen.getByLabelText("Requerimento:"), "150288");
    await waitFor(() =>
      expect(mocks.consultarRequerimento).toHaveBeenCalledWith(150288, expect.anything()),
    );
    expect(
      await screen.findByText("✓ Requerimento encontrado.", undefined, { timeout: 2000 }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("Nome:")).toHaveValue("Queijo Mussarela Flora Milk");
    expect(screen.getByLabelText("Cliente:")).toHaveValue("Laticinios Florida Ltda");
    expect(screen.getByLabelText("Vendedor:")).toHaveValue("Regislaine Petrim");
    // travados (somente leitura)
    expect(screen.getByLabelText("Nome:")).toHaveAttribute("readonly");
  });

  it("exibe a imagem do requerimento (proxy do share) após resolver", async () => {
    const user = userEvent.setup();
    renderView();

    await resolverRequerimento(user);
    await waitFor(() =>
      expect(mocks.baixarArteRequerimento).toHaveBeenCalledWith(150288, expect.anything()),
    );
    const img = (await screen.findByAltText(
      "Arte do requerimento 150288",
    )) as HTMLImageElement;
    expect(img.getAttribute("src")).toMatch(/^blob:/); // objectURL, nunca URL do share
  });

  it("imagem indisponível no share mostra aviso, sem quebrar o form", async () => {
    mocks.baixarArteRequerimento.mockRejectedValue(
      new ApiError(422, "arte_indisponivel", "Imagem indisponível."),
    );
    const user = userEvent.setup();
    renderView();

    await resolverRequerimento(user);
    expect(
      await screen.findByText("Imagem indisponível para este requerimento."),
    ).toBeInTheDocument();
  });

  it("requerimento inexistente (404) mostra erro e não deixa criar", async () => {
    mocks.consultarRequerimento.mockRejectedValue(
      new ApiError(404, "requerimento_nao_encontrado", "Requerimento não encontrado."),
    );
    const user = userEvent.setup();
    renderView();

    await user.type(screen.getByLabelText("Requerimento:"), "999999");
    expect(
      await screen.findByText("Requerimento não encontrado no ERP.", undefined, { timeout: 2000 }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Matriz" }));
    await user.click(screen.getByRole("button", { name: "Criar Prova" }));
    expect(mocks.criarProva).not.toHaveBeenCalled();
  });

  it("submeter sem requerimento e sem rota mostra erros e não chama a API", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole("button", { name: "Criar Prova" }));

    expect(screen.getByText("Selecione a rota de encaminhamento.")).toBeInTheDocument();
    expect(
      screen.getByText("Informe um número de requerimento válido e encontrado."),
    ).toBeInTheDocument();
    expect(mocks.criarProva).not.toHaveBeenCalled();
  });

  it("caminho feliz (DP-7): cria por requerimento, toast, baixa etiqueta e navega", async () => {
    const user = userEvent.setup();
    renderView();

    await resolverRequerimento(user);
    await user.click(screen.getByRole("radio", { name: "Matriz" }));
    await user.click(screen.getByRole("button", { name: "Criar Prova" }));

    await waitFor(() => expect(mocks.criarProva).toHaveBeenCalledTimes(1));
    expect(mocks.criarProva.mock.calls[0][0]).toMatchObject({ codReqArt: 150288, rota: "matriz" });
    // RNF-015: envia uma chave de idempotência (provaId).
    expect(mocks.criarProva.mock.calls[0][0].provaId).toEqual(expect.any(String));
    expect(await screen.findByText("Prova PRV-2026-06-K3T9XB criada.")).toBeInTheDocument();
    await waitFor(() => expect(mocks.baixarEtiqueta).toHaveBeenCalledWith(PROVA.id));
    expect(mocks.salvarArquivo).toHaveBeenCalledWith(
      expect.any(Blob),
      "etiqueta-PRV-2026-06-K3T9XB.pdf",
    );
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/provas"));
    expect(screen.getByRole("button", { name: "Criando…" })).toBeDisabled();
  });

  it("radiogroup de Rota: setas movem e selecionam (WAI-ARIA APG)", async () => {
    const user = userEvent.setup();
    renderView();

    const matriz = screen.getByRole("radio", { name: "Matriz" });
    matriz.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "Filial" })).toHaveAttribute("aria-checked", "true");
    await user.keyboard("{End}");
    expect(screen.getByRole("radio", { name: "Lam. Filial" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "Matriz" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Matriz" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Filial" })).toHaveAttribute("tabindex", "-1");
  });

  it("erro da API na criação vira toast e o formulário segue editável", async () => {
    mocks.criarProva.mockRejectedValue(
      new ApiError(
        422,
        "vendedor_nao_mapeado",
        "O vendedor deste requerimento não está cadastrado no sistema.",
      ),
    );
    const user = userEvent.setup();
    renderView();

    await resolverRequerimento(user);
    await user.click(screen.getByRole("radio", { name: "Matriz" }));
    await user.click(screen.getByRole("button", { name: "Criar Prova" }));

    expect(
      await screen.findByText("O vendedor deste requerimento não está cadastrado no sistema."),
    ).toBeInTheDocument();
    expect(mocks.push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Criar Prova" })).toBeEnabled();
  });

  it("falha SÓ no download: painel de retry, sem navegar; retry baixa e navega", async () => {
    mocks.baixarEtiqueta.mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "offline"));
    const user = userEvent.setup();
    renderView();

    await resolverRequerimento(user);
    await user.click(screen.getByRole("radio", { name: "Matriz" }));
    await user.click(screen.getByRole("button", { name: "Criar Prova" }));

    expect(
      await screen.findByRole("heading", { name: "Prova PRV-2026-06-K3T9XB criada" }),
    ).toBeInTheDocument();
    expect(mocks.push).not.toHaveBeenCalled();

    mocks.baixarEtiqueta.mockResolvedValueOnce(new Blob(["%PDF"]));
    await user.click(screen.getByRole("button", { name: "Baixar etiqueta" }));
    await waitFor(() => expect(mocks.salvarArquivo).toHaveBeenCalled());
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/provas"));
  });
});
