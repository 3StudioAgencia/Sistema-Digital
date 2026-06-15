import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import type { PaginaProvas, ProvaListagem } from "@/lib/api/provas";

// Mock controlável de next/navigation: `nav.search` simula a query da URL;
// replace/push são espionados (o estado de filtros é escrito na URL — DP-5).
const nav = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn(), search: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: nav.push }),
  usePathname: () => "/provas",
  useSearchParams: () => new URLSearchParams(nav.search),
}));

const mocks = vi.hoisted(() => ({
  listarProvas: vi.fn(),
  listarVendedoresProvas: vi.fn(),
}));
vi.mock("@/lib/api/provas", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/provas")>();
  return { ...original, ...mocks };
});

import { ProvasView } from "./provas-view";

const P1: ProvaListagem = {
  id: "p1",
  codigo: "PRV-2026-04-AAAAAA",
  nome: "Embalagem premium granola",
  requerimento: "123456",
  cliente: "Moacyr",
  vendedor_id: "v1",
  vendedor_nome: "Regiane",
  rota: "matriz",
  status: "cancelada",
  created_at: "2026-04-09T12:00:00Z",
  finalizada_em: null,
};
const P2: ProvaListagem = {
  ...P1,
  id: "p2",
  requerimento: "998877",
  cliente: "Cocatrel",
  vendedor_nome: "Packon",
  rota: "filial",
  status: "aprovada_vendedor",
};

function pagina(items: ProvaListagem[], total = items.length): PaginaProvas {
  return { items, total, page: 1, page_size: 20 };
}

beforeEach(() => {
  nav.replace.mockReset();
  nav.push.mockReset();
  nav.search = "";
  mocks.listarProvas.mockReset();
  mocks.listarVendedoresProvas.mockReset();
  mocks.listarProvas.mockResolvedValue(pagina([P1, P2]));
  mocks.listarVendedoresProvas.mockResolvedValue([
    { id: "v1", nome: "Regiane" },
    { id: "v2", nome: "Packon" },
  ]);
});

describe("ProvasView (W2-C07)", () => {
  it("renderiza a tabela fiel ao design: colunas, rótulos e ação 'Ver' por linha", async () => {
    render(<ProvasView escopo="todas" />);

    const tabela = screen.getByRole("table", { name: "Provas" });
    for (const coluna of [
      "Requerimento",
      "Nome",
      "Cliente",
      "Vendedor",
      "Status",
      "Rota",
      "Criada em",
    ]) {
      expect(within(tabela).getByRole("columnheader", { name: coluna })).toBeInTheDocument();
    }

    const linha = (await within(tabela).findByText("Moacyr")).closest(
      '[role="row"]',
    ) as HTMLElement;
    expect(within(linha).getByText("123456")).toBeInTheDocument();
    expect(within(linha).getByText("Regiane")).toBeInTheDocument();
    expect(within(linha).getByText("Cancelada")).toBeInTheDocument(); // rótulo do status (DP-4)
    expect(within(linha).getByText("Matriz")).toBeInTheDocument(); // rótulo da rota
    expect(within(linha).getByText("09-04-2026")).toBeInTheDocument(); // data formatada
    expect(within(linha).getByRole("button", { name: "Ver" })).toBeInTheDocument();
  });

  it("busca aplica debounce ≥300ms e só então escreve na URL (RNF-023)", async () => {
    vi.useFakeTimers();
    try {
      render(<ProvasView escopo="todas" />);
      await act(async () => {
        await vi.runOnlyPendingTimersAsync();
      });
      expect(mocks.listarProvas).toHaveBeenCalledTimes(1); // só a 1ª página no mount
      nav.replace.mockClear();

      const campo = screen.getByLabelText("Buscar por nome ou requerimento");
      fireEvent.change(campo, { target: { value: "gra" } });
      fireEvent.change(campo, { target: { value: "granola" } });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(250);
      });
      expect(nav.replace).not.toHaveBeenCalled(); // ainda dentro do debounce

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      expect(nav.replace).toHaveBeenCalledTimes(1);
      expect(nav.replace.mock.calls[0][0]).toContain("busca=granola");
      // Nenhuma requisição extra por tecla (a URL mockada não muda → sem refetch).
      expect(mocks.listarProvas).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("hidrata os filtros da URL no mount — refresh preserva os filtros (DP-5)", async () => {
    nav.search = "busca=granola&status=aprovada_vendedor";
    render(<ProvasView escopo="todas" />);

    await waitFor(() =>
      expect(mocks.listarProvas.mock.calls[0][0]).toMatchObject({
        busca: "granola",
        status: "aprovada_vendedor",
        page: 1,
      }),
    );
    expect(screen.getByLabelText("Buscar por nome ou requerimento")).toHaveValue("granola");
  });

  it("filtro de Status escreve o valor do enum na URL", async () => {
    const user = userEvent.setup();
    render(<ProvasView escopo="todas" />);
    await screen.findByText("Moacyr");

    await user.click(screen.getByRole("button", { name: "Filtrar por status" }));
    await user.click(await screen.findByRole("option", { name: "Aprovada" }));

    await waitFor(() =>
      expect(nav.replace.mock.calls.at(-1)?.[0]).toContain("status=aprovada_vendedor"),
    );
  });

  it("adapta a barra por perfil (DP-2): esconde 'Vendedor' quando o escopo é 'as próprias'", async () => {
    const { rerender } = render(<ProvasView escopo="proprias" />);
    await screen.findByText("Moacyr");
    expect(screen.queryByRole("button", { name: "Filtrar por vendedor" })).not.toBeInTheDocument();
    expect(mocks.listarVendedoresProvas).not.toHaveBeenCalled();

    rerender(<ProvasView escopo="todas" />);
    expect(await screen.findByRole("button", { name: "Filtrar por vendedor" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.listarVendedoresProvas).toHaveBeenCalled());
  });

  it("'Limpar' zera os inputs e a query da URL", async () => {
    const user = userEvent.setup();
    nav.search = "busca=granola";
    render(<ProvasView escopo="todas" />);
    await screen.findByText("Moacyr");
    expect(screen.getByLabelText("Buscar por nome ou requerimento")).toHaveValue("granola");

    await user.click(screen.getByRole("button", { name: "Limpar" }));

    expect(nav.replace).toHaveBeenCalledWith("/provas", { scroll: false }); // sem query
    expect(screen.getByLabelText("Buscar por nome ou requerimento")).toHaveValue("");
  });

  it("'Ver' navega para o detalhe /provas/{id} (placeholder até o C08 — DP-6)", async () => {
    const user = userEvent.setup();
    render(<ProvasView escopo="todas" />);
    const linha = (await screen.findByText("Moacyr")).closest('[role="row"]') as HTMLElement;

    await user.click(within(linha).getByRole("button", { name: "Ver" }));

    expect(nav.push).toHaveBeenCalledWith("/provas/p1");
  });

  it("estado vazio: sem resultados mostra a mensagem", async () => {
    mocks.listarProvas.mockResolvedValue(pagina([]));
    render(<ProvasView escopo="todas" />);
    // Mensagem aparece na tabela (desktop) e nos cards (mobile).
    expect(await screen.findAllByText("Nenhuma prova encontrada.")).not.toHaveLength(0);
  });

  it("falha de rede mostra erro com retry", async () => {
    mocks.listarProvas.mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "API fora."));
    render(<ProvasView escopo="todas" />);
    expect(await screen.findByText(/não foi possível carregar as provas/i)).toBeInTheDocument();

    mocks.listarProvas.mockResolvedValue(pagina([P1]));
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(await screen.findByText("Moacyr")).toBeInTheDocument();
  });

  it("403 do backend mostra acesso negado (anti-enumeração)", async () => {
    mocks.listarProvas.mockRejectedValue(new ApiError(403, "http_error", "Acesso negado."));
    render(<ProvasView escopo="todas" />);
    expect(await screen.findByText(/você não tem acesso a esta listagem/i)).toBeInTheDocument();
  });
});
