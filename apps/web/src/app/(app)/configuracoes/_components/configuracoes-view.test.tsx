import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { Configuracao } from "@/lib/api/configuracoes";

const mocks = vi.hoisted(() => ({
  listarConfiguracoes: vi.fn(),
  salvarConfiguracao: vi.fn(),
}));

vi.mock("@/lib/api/configuracoes", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/configuracoes")>();
  return {
    ...original,
    listarConfiguracoes: mocks.listarConfiguracoes,
    salvarConfiguracao: mocks.salvarConfiguracao,
  };
});

import { ConfiguracoesView } from "./configuracoes-view";

const DELAY: Configuracao = {
  chave: "delay_horas_uteis",
  valor: 48,
  default: 48,
  descricao: "Uma prova digital sem movimentação por mais que esse tempo é considerada atrasada.",
  atualizado_em: null,
  atualizado_por: null,
};

const ETIQUETA: Configuracao = {
  chave: "etiqueta_template",
  valor: {
    modo: "padrao",
    largura: 95,
    altura: 55,
    margem: 3,
    fonte: "helvetica",
    qr_zona_quieta_modulos: 2,
  },
  default: {
    modo: "padrao",
    largura: 95,
    altura: 55,
    margem: 3,
    fonte: "helvetica",
    qr_zona_quieta_modulos: 2,
  },
  descricao: "Template da etiqueta imprimível: layout padrão ou personalizado.",
  atualizado_em: null,
  atualizado_por: null,
};

function renderView() {
  return render(
    <ToastProvider>
      <ConfiguracoesView />
    </ToastProvider>,
  );
}

function cardDelay() {
  return within(screen.getByRole("region", { name: "Tempo de atraso" }));
}

function cardEtiqueta() {
  return within(screen.getByRole("region", { name: "Template de etiqueta" }));
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
  mocks.listarConfiguracoes.mockResolvedValue([DELAY, ETIQUETA]);
  mocks.salvarConfiguracao.mockImplementation((chave: string, valor: unknown) =>
    Promise.resolve({
      chave,
      valor,
      default: chave === "delay_horas_uteis" ? 48 : ETIQUETA.default,
      descricao: chave === "delay_horas_uteis" ? DELAY.descricao : ETIQUETA.descricao,
      atualizado_em: "2026-06-15T12:00:00Z",
      atualizado_por: "admin-1",
    }),
  );
});

describe("ConfiguracoesView (W2-C09)", () => {
  it("renderiza o título e os dois cards com os valores carregados", async () => {
    renderView();
    expect(screen.getByRole("heading", { name: "Configurações do sistema" })).toBeInTheDocument();

    expect(await screen.findByRole("region", { name: "Tempo de atraso" })).toBeInTheDocument();
    expect(cardDelay().getByLabelText("Tempo (horas úteis)")).toHaveValue("48");
    expect(cardDelay().getByText(/sem movimentação por mais que esse tempo/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Template de etiqueta" })).toBeInTheDocument();
    // dois "Salvar" — um por card (save granular)
    expect(screen.getAllByRole("button", { name: "Salvar" })).toHaveLength(2);
  });

  it("salva o tempo de atraso (US-016) e mostra toast de sucesso", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("region", { name: "Tempo de atraso" });

    const input = cardDelay().getByLabelText("Tempo (horas úteis)");
    await user.clear(input);
    await user.type(input, "72");
    await user.click(cardDelay().getByRole("button", { name: "Salvar" }));

    await waitFor(() =>
      expect(mocks.salvarConfiguracao).toHaveBeenCalledWith("delay_horas_uteis", 72),
    );
    expect(await screen.findByText("Configurações salvas.")).toBeInTheDocument();
  });

  it("valida o tempo de atraso em tempo real e não chama a API quando inválido", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("region", { name: "Tempo de atraso" });

    const input = cardDelay().getByLabelText("Tempo (horas úteis)");
    await user.clear(input);
    await user.type(input, "0");
    await user.click(cardDelay().getByRole("button", { name: "Salvar" }));

    expect(cardDelay().getByText("O tempo deve ser maior que zero.")).toBeInTheDocument();
    expect(mocks.salvarConfiguracao).not.toHaveBeenCalled();
  });

  it("template personalizado revela os campos e salva o objeto (RN-011/DP-5)", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("region", { name: "Template de etiqueta" });

    // padrão: campos escondidos
    expect(cardEtiqueta().queryByLabelText("Largura (mm)")).not.toBeInTheDocument();

    await user.click(cardEtiqueta().getByRole("radio", { name: "Personalizado" }));
    const largura = await cardEtiqueta().findByLabelText("Largura (mm)");
    await user.clear(largura);
    await user.type(largura, "100");
    await user.click(cardEtiqueta().getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(mocks.salvarConfiguracao).toHaveBeenCalledTimes(1));
    const [chave, valor] = mocks.salvarConfiguracao.mock.calls[0];
    expect(chave).toBe("etiqueta_template");
    // Trava os 5 campos espelhados do C06 (DP-5): dropar qualquer um cairia em
    // default server-side, ignorando a edição do usuário em silêncio.
    expect(valor).toEqual({
      modo: "personalizado",
      largura: 100,
      altura: 55,
      margem: 3,
      fonte: "helvetica",
      qr_zona_quieta_modulos: 2,
    });
  });

  it("salva o template no modo padrão (caminho comum) com os defaults", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("region", { name: "Template de etiqueta" });

    // Não troca o modo: salva direto no padrão (o caminho que o usuário mais usa).
    await user.click(cardEtiqueta().getByRole("button", { name: "Salvar" }));

    await waitFor(() =>
      expect(mocks.salvarConfiguracao).toHaveBeenCalledWith(
        "etiqueta_template",
        expect.objectContaining({ modo: "padrao", largura: 95, altura: 55 }),
      ),
    );
  });

  it("o segmented control de Modo é navegável por teclado (WAI-ARIA radiogroup)", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findByRole("region", { name: "Template de etiqueta" });

    const padrao = cardEtiqueta().getByRole("radio", { name: "Padrão" });
    padrao.focus();
    await user.keyboard("{ArrowRight}");
    expect(cardEtiqueta().getByRole("radio", { name: "Personalizado" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    // os campos do personalizado aparecem ao selecionar por teclado
    expect(await cardEtiqueta().findByLabelText("Largura (mm)")).toBeInTheDocument();
    await user.keyboard("{ArrowRight}"); // wrap → Padrão
    expect(cardEtiqueta().getByRole("radio", { name: "Padrão" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("respeita prefers-reduced-motion (degrada sem quebrar — AC §6.5/DoD)", async () => {
    const original = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    try {
      const user = userEvent.setup();
      renderView();
      await screen.findByRole("region", { name: "Template de etiqueta" });
      // comportamento preservado com a animação suprimida: revela campos e salva
      await user.click(cardEtiqueta().getByRole("radio", { name: "Personalizado" }));
      expect(await cardEtiqueta().findByLabelText("Largura (mm)")).toBeInTheDocument();
      await user.click(cardDelay().getByRole("button", { name: "Salvar" }));
      await waitFor(() =>
        expect(mocks.salvarConfiguracao).toHaveBeenCalledWith("delay_horas_uteis", 48),
      );
    } finally {
      window.matchMedia = original;
    }
  });

  it("nega acesso a não-3Studio (403 → estado restrito)", async () => {
    mocks.listarConfiguracoes.mockRejectedValueOnce(
      new ApiError(403, "http_error", "Acesso negado."),
    );
    renderView();
    expect(await screen.findByText(/Acesso restrito/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Tempo de atraso" })).not.toBeInTheDocument();
  });

  it("mostra erro com retry quando a carga falha", async () => {
    mocks.listarConfiguracoes.mockRejectedValueOnce(new ApiError(0, "api_inacessivel", "offline"));
    const user = userEvent.setup();
    renderView();

    const retry = await screen.findByRole("button", { name: "Tentar novamente" });
    mocks.listarConfiguracoes.mockResolvedValueOnce([DELAY, ETIQUETA]);
    await user.click(retry);

    expect(await screen.findByRole("region", { name: "Tempo de atraso" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.listarConfiguracoes).toHaveBeenCalledTimes(2));
  });
});
