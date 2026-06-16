import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast/ToastProvider";
import { ApiError } from "@/lib/api/client";
import type { ProvaDetalhe } from "@/lib/api/provas";

const mocks = vi.hoisted(() => ({
  obterProva: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace, back: mocks.back }),
}));

vi.mock("@/lib/api/provas", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/provas")>();
  return { ...original, obterProva: mocks.obterProva };
});

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

function renderView() {
  return render(
    <ToastProvider>
      <ConfirmarView provaId="p-1" />
    </ToastProvider>,
  );
}

beforeEach(() => {
  for (const m of Object.values(mocks)) m.mockReset();
  mocks.obterProva.mockResolvedValue(PROVA);
});

describe("ConfirmarView (W3-C10/DP-2)", () => {
  it("mostra nome + requerimento + placeholder de assinatura (C12) e confirmação travada (C11)", async () => {
    renderView();
    expect(
      await screen.findByRole("heading", { name: "Mussarela fatiada", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Requerimento: 155295")).toBeInTheDocument();
    expect(screen.getByText(/captura de assinatura chega com o componente/i)).toBeInTheDocument();
    // O passo de confirmação é placeholder (C11): botão desabilitado.
    expect(screen.getByRole("button", { name: "Confirmar movimentação" })).toBeDisabled();
  });

  it("404 (inexistente OU fora do escopo) → toast genérico + volta ao escaneamento (§11)", async () => {
    mocks.obterProva.mockRejectedValue(
      new ApiError(404, "prova_nao_encontrada", "Prova não encontrada."),
    );
    renderView();
    expect(await screen.findByText("Prova não encontrada.")).toBeInTheDocument(); // toast
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/escanear"));
  });
});
