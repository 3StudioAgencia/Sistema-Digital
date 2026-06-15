import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import { ARTE_TAMANHO_MAXIMO, type Prova } from "@/lib/api/provas";
import type { PaginaUsuarios, Usuario } from "@/lib/api/usuarios";

const mocks = vi.hoisted(() => ({
  listarUsuarios: vi.fn(),
  criarProva: vi.fn(),
  baixarEtiqueta: vi.fn(),
  salvarArquivo: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/api/usuarios", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/usuarios")>();
  return { ...original, listarUsuarios: mocks.listarUsuarios };
});

vi.mock("@/lib/api/provas", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/provas")>();
  return {
    ...original,
    criarProva: mocks.criarProva,
    baixarEtiqueta: mocks.baixarEtiqueta,
    salvarArquivo: mocks.salvarArquivo,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

import { NovaProvaView } from "./nova-prova-view";

const RENAN: Usuario = {
  id: "v-renan",
  nome: "Renan Petrim",
  email: "renan@x.y",
  setor: "vendedor",
  localizacao: "matriz",
  administrador: false,
  ativo: true,
  created_at: null,
  updated_at: null,
};

const PROVA: Prova = {
  id: "p-1",
  codigo: "PRV-2026-06-K3T9XB",
  nome: "Etiq Cafe Caproni Classico",
  requerimento: "155295",
  cliente: "Cafe Caproni",
  vendedor_id: RENAN.id,
  rota: "matriz",
  status: "criada",
  created_at: "2026-06-12T00:00:00Z",
};

function paginaVendedores(items: Usuario[]): PaginaUsuarios {
  return { items, total: items.length, page: 1, page_size: 100 };
}

function arquivoJpegValido(nome = "arte.jpg"): File {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0])], nome, { type: "image/jpeg" });
}

function renderView() {
  return render(
    <ToastProvider>
      <NovaProvaView />
    </ToastProvider>,
  );
}

function inputDeArquivo(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector('input[type="file"]');
  expect(input).not.toBeNull();
  return input as HTMLInputElement;
}

async function preencherFormularioValido(container: HTMLElement) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nome"), "Etiq Cafe Caproni Classico");
  await user.type(screen.getByLabelText("Requerimento"), "155295");
  await user.type(screen.getByLabelText("Cliente"), "Cafe Caproni");
  // Dropdown custom de vendedor (nome acessível = rótulo "Vendedor")
  await user.click(screen.getByRole("button", { name: "Vendedor" }));
  await user.click(await screen.findByRole("option", { name: "Renan Petrim" }));
  // Segmented control de rota
  await user.click(screen.getByRole("radio", { name: "Matriz" }));
  fireEvent.change(inputDeArquivo(container), { target: { files: [arquivoJpegValido()] } });
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.listarUsuarios.mockResolvedValue(paginaVendedores([RENAN]));
  mocks.criarProva.mockResolvedValue(PROVA);
  mocks.baixarEtiqueta.mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
});

describe("NovaProvaView (W2-C06)", () => {
  it("renderiza fiel ao design: título, botão, campos, rota (4 opções) e dropzone", async () => {
    renderView();

    expect(screen.getByRole("heading", { name: "Nova prova Digital" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar Prova" })).toBeInTheDocument();
    for (const rotulo of ["Nome", "Requerimento", "Cliente"]) {
      expect(screen.getByLabelText(rotulo)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "Vendedor" })).toBeInTheDocument();
    // ordem do design: Matriz · Filial · Lam. Matriz · Lam. Filial
    const opcoes = screen.getAllByRole("radio");
    expect(opcoes.map((o) => o.textContent)).toEqual([
      "Matriz",
      "Filial",
      "Lam. Matriz",
      "Lam. Filial",
    ]);
    expect(screen.getByText("Solte ou clique")).toBeInTheDocument();
    expect(screen.getByText("JPG • PNG")).toBeInTheDocument();
    // vendedores carregados em UMA consulta, já filtrada server-side
    await waitFor(() => expect(mocks.listarUsuarios).toHaveBeenCalledTimes(1));
    expect(mocks.listarUsuarios.mock.calls[0][0]).toMatchObject({
      setor: "vendedor",
      status: "ativo",
      page: 1,
    });
  });

  it("submeter vazio mostra erros claros (incl. rota — critério §6.1) e não chama a API", async () => {
    const user = userEvent.setup();
    renderView();

    await user.click(screen.getByRole("button", { name: "Criar Prova" }));

    expect(screen.getByText("Selecione a rota de encaminhamento.")).toBeInTheDocument();
    expect(screen.getByText("Informe o nome da prova.")).toBeInTheDocument();
    expect(screen.getByText("Informe o número do requerimento.")).toBeInTheDocument();
    expect(screen.getByText("Informe o cliente.")).toBeInTheDocument();
    expect(screen.getByText("Selecione o vendedor responsável.")).toBeInTheDocument();
    expect(screen.getByText("Anexe a arte da prova (JPG ou PNG, até 10 MB).")).toBeInTheDocument();
    expect(mocks.criarProva).not.toHaveBeenCalled();
  });

  it("valida em tempo real: erro de requerimento não numérico e limpeza ao corrigir", async () => {
    const user = userEvent.setup();
    renderView();

    await user.type(screen.getByLabelText("Requerimento"), "ABC");
    await user.click(screen.getByRole("button", { name: "Criar Prova" }));
    expect(screen.getByText("O requerimento aceita apenas números.")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Requerimento"));
    await user.type(screen.getByLabelText("Requerimento"), "123");
    expect(screen.queryByText("O requerimento aceita apenas números.")).not.toBeInTheDocument();
  });

  it("dropzone rejeita tipo não permitido e arquivo acima de 10 MB", async () => {
    const { container } = renderView();
    const input = inputDeArquivo(container);

    const gif = new File([new Uint8Array([0x47, 0x49, 0x46])], "arte.gif", { type: "image/gif" });
    fireEvent.change(input, { target: { files: [gif] } });
    expect(await screen.findByText("Apenas arquivos JPG ou PNG.")).toBeInTheDocument();

    const grande = arquivoJpegValido("grande.jpg");
    Object.defineProperty(grande, "size", { value: ARTE_TAMANHO_MAXIMO + 1 });
    fireEvent.change(input, { target: { files: [grande] } });
    expect(
      await screen.findByText("O arquivo excede o tamanho máximo de 10 MB."),
    ).toBeInTheDocument();

    // arquivo válido substitui o erro pelo nome/tamanho
    fireEvent.change(input, { target: { files: [arquivoJpegValido()] } });
    expect(await screen.findByText("arte.jpg")).toBeInTheDocument();
  });

  it("caminho feliz (DP-7): cria, toast de sucesso, baixa a etiqueta e navega", async () => {
    const user = userEvent.setup();
    const { container } = renderView();
    await screen.findByRole("button", { name: "Vendedor" });

    await preencherFormularioValido(container);
    await user.click(screen.getByRole("button", { name: "Criar Prova" }));

    await waitFor(() => expect(mocks.criarProva).toHaveBeenCalledTimes(1));
    expect(mocks.criarProva.mock.calls[0][0]).toMatchObject({
      nome: "Etiq Cafe Caproni Classico",
      requerimento: "155295",
      cliente: "Cafe Caproni",
      vendedorId: RENAN.id,
      rota: "matriz",
    });
    // RNF-015: envia uma chave de idempotência (prova_id) para o backend.
    expect(mocks.criarProva.mock.calls[0][0].provaId).toEqual(expect.any(String));
    expect(await screen.findByText("Prova PRV-2026-06-K3T9XB criada.")).toBeInTheDocument();
    await waitFor(() => expect(mocks.baixarEtiqueta).toHaveBeenCalledWith(PROVA.id));
    expect(mocks.salvarArquivo).toHaveBeenCalledWith(
      expect.any(Blob),
      "etiqueta-PRV-2026-06-K3T9XB.pdf",
    );
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/provas"));
    // o botão NÃO reabilita na navegação em voo (sem janela de duplo submit)
    expect(screen.getByRole("button", { name: "Criando…" })).toBeDisabled();
  });

  it("radiogroup de Rota: setas movem e selecionam (WAI-ARIA APG)", async () => {
    const user = userEvent.setup();
    renderView();

    const matriz = screen.getByRole("radio", { name: "Matriz" });
    matriz.focus();
    await user.keyboard("{ArrowRight}"); // Matriz → Filial
    expect(screen.getByRole("radio", { name: "Filial" })).toHaveAttribute("aria-checked", "true");
    await user.keyboard("{End}"); // → Lam. Filial (último)
    expect(screen.getByRole("radio", { name: "Lam. Filial" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.keyboard("{ArrowRight}"); // wrap → Matriz
    expect(screen.getByRole("radio", { name: "Matriz" })).toHaveAttribute("aria-checked", "true");
    // roving tabindex: só a opção ativa é tab stop
    expect(screen.getByRole("radio", { name: "Matriz" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Filial" })).toHaveAttribute("tabindex", "-1");
  });

  it("erro da API vira toast e o formulário segue editável (sem perder dados)", async () => {
    mocks.criarProva.mockRejectedValue(
      new ApiError(422, "vendedor_invalido", "Vendedor responsável inválido."),
    );
    const user = userEvent.setup();
    const { container } = renderView();
    await screen.findByRole("button", { name: "Vendedor" });

    await preencherFormularioValido(container);
    await user.click(screen.getByRole("button", { name: "Criar Prova" }));

    expect(await screen.findByText("Vendedor responsável inválido.")).toBeInTheDocument();
    expect(mocks.push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Criar Prova" })).toBeEnabled();
    expect(screen.getByLabelText("Nome")).toHaveValue("Etiq Cafe Caproni Classico");
  });

  it("falha SÓ no download: painel de retry, sem navegar; retry baixa e navega", async () => {
    mocks.baixarEtiqueta.mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "offline"));
    const user = userEvent.setup();
    const { container } = renderView();
    await screen.findByRole("button", { name: "Vendedor" });

    await preencherFormularioValido(container);
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

  it("falha ao carregar vendedores mostra retry e refaz a consulta", async () => {
    mocks.listarUsuarios.mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "offline"));
    const user = userEvent.setup();
    renderView();

    const retry = await screen.findByRole("button", {
      name: "Falha ao carregar vendedores — tentar novamente",
    });
    mocks.listarUsuarios.mockResolvedValueOnce(paginaVendedores([RENAN]));
    await user.click(retry);

    expect(await screen.findByRole("button", { name: "Vendedor" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.listarUsuarios).toHaveBeenCalledTimes(2));
  });
});
