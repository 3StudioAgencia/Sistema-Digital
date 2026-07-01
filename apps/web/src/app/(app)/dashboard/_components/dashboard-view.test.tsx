import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Dashboard } from "../../../../lib/api/dashboard";

// Router espionado (cliques nos cards/atalhos navegam — DP-6/DP-3).
const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: nav.push }) }));

// Refetch do dashboard (chamado no Realtime / na carga sem SSR).
const mocks = vi.hoisted(() => ({ fetchDashboard: vi.fn() }));
vi.mock("@/lib/api/dashboard", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../../lib/api/dashboard")>();
  return { ...original, fetchDashboard: mocks.fetchDashboard };
});

// Fake do Realtime: captura o callback de postgres_changes e conta subscriptions.
const rt = vi.hoisted(() => ({
  handler: null as null | ((p: unknown) => void),
  channels: 0,
  subscribes: 0,
  removed: 0,
}));
vi.mock("@/lib/supabase/client", () => ({
  getSupabaseBrowserClient: () => ({
    channel: () => {
      rt.channels += 1;
      const ch = {
        on: (_e: string, _c: unknown, cb: (p: unknown) => void) => {
          rt.handler = cb;
          return ch;
        },
        subscribe: () => {
          rt.subscribes += 1;
          return ch;
        },
      };
      return ch;
    },
    removeChannel: () => {
      rt.removed += 1;
    },
  }),
}));

import { DashboardView } from "./dashboard-view";

const DADOS: Dashboard = {
  criadas_hoje: 25,
  com_vendedor: 6894,
  aprovadas: 5487,
  na_clicheria: 5,
  atrasadas_total: 258,
  atrasadas_por_vendedor: [
    { vendedor_id: "v1", vendedor_nome: "Regiane", total: 24 },
    { vendedor_id: "v2", vendedor_nome: "Packon", total: 12 },
  ],
};

beforeEach(() => {
  nav.push.mockReset();
  mocks.fetchDashboard.mockReset();
  rt.handler = null;
  rt.channels = 0;
  rt.subscribes = 0;
  rt.removed = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("DashboardView (W4-C16)", () => {
  it("renderiza o bento fiel ao design: 5 contadores + Atrasadas (lista+total) + atalhos", () => {
    render(<DashboardView inicial={DADOS} podeCriarProva />);

    for (const titulo of [
      "Criadas hoje",
      "Com Vendedor",
      "Aprovadas",
      "Na clicheria",
      "Atrasadas",
    ]) {
      expect(screen.getByText(titulo)).toBeInTheDocument();
    }
    // Números via aria-label do AnimatedCounter (estável, independe do count-up).
    expect(screen.getByLabelText("25")).toBeInTheDocument();
    expect(screen.getByLabelText("6894")).toBeInTheDocument();
    expect(screen.getByLabelText("5487")).toBeInTheDocument();
    expect(screen.getByLabelText("258")).toBeInTheDocument();
    // Atrasadas é uma LISTA por vendedor (≠ dos demais cards).
    const lista = screen.getByRole("list", { name: "Atrasadas por vendedor" });
    expect(within(lista).getByText("Regiane")).toBeInTheDocument();
    expect(within(lista).getByText("24")).toBeInTheDocument();
    expect(within(lista).getByText("Packon")).toBeInTheDocument();
    // Atalhos.
    expect(screen.getByText("Escanear QR Code")).toBeInTheDocument();
    expect(screen.getByText("Nova Prova")).toBeInTheDocument();
  });

  it("usa UMA única subscription do Realtime (RNF-021) e limpa no unmount", () => {
    const { unmount } = render(<DashboardView inicial={DADOS} podeCriarProva />);
    expect(rt.channels).toBe(1);
    expect(rt.subscribes).toBe(1);
    unmount();
    expect(rt.removed).toBe(1);
  });

  it("evento Realtime dispara UM refetch (debounced) e atualiza os números", async () => {
    vi.useFakeTimers();
    mocks.fetchDashboard.mockResolvedValue({ ...DADOS, criadas_hoje: 26 });
    render(<DashboardView inicial={DADOS} podeCriarProva />);
    expect(screen.getByLabelText("25")).toBeInTheDocument();

    // Rajada de eventos → um só refetch após o debounce.
    act(() => {
      rt.handler?.({});
      rt.handler?.({});
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    // Sob fake timers, waitFor entra em deadlock (poll por timer): asserção direta
    // após o flush do debounce + microtasks do refetch.
    expect(mocks.fetchDashboard).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("26")).toBeInTheDocument();
  });

  it("queda do Realtime degrada graciosamente: mantém o último valor (sem crash)", async () => {
    vi.useFakeTimers();
    mocks.fetchDashboard.mockRejectedValue(new Error("realtime caiu"));
    render(<DashboardView inicial={DADOS} podeCriarProva />);

    act(() => rt.handler?.({}));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    // Último valor preservado (não some, não quebra a tela).
    expect(screen.getByLabelText("25")).toBeInTheDocument();
  });

  it("clica em 'Com Vendedor' → listagem pré-filtrada por múltiplos status (DP-6)", async () => {
    const user = userEvent.setup();
    render(<DashboardView inicial={DADOS} podeCriarProva />);

    await user.click(screen.getByText("Com Vendedor"));
    expect(nav.push).toHaveBeenCalledWith(
      "/provas?status=retirada_vendedor&status=encaminhada_para_vendedor",
    );
  });

  it("clica numa linha de Atrasadas → listagem atrasada + vendedor (DP-6)", async () => {
    const user = userEvent.setup();
    render(<DashboardView inicial={DADOS} podeCriarProva />);

    await user.click(screen.getByText("Regiane"));
    expect(nav.push).toHaveBeenCalledWith("/provas?atrasada=true&vendedor=v1");
  });

  it("atalho 'Nova Prova' some para quem não é 3Studio (RF-017/DP-3)", () => {
    render(<DashboardView inicial={DADOS} podeCriarProva={false} />);
    expect(screen.queryByText("Nova Prova")).not.toBeInTheDocument();
    expect(screen.getByText("Escanear QR Code")).toBeInTheDocument(); // Escanear é universal
  });

  // Corte do C18 (Atalhos Rápidos) — decisão de produto: NÃO existe atalho de
  // Relatórios. Relatórios é acessível só pela sidebar (3Studio). Este guard
  // falharia se um atalho/CTA de relatórios reaparecesse no dashboard.
  it("corte do C18: nenhum atalho/CTA do dashboard leva a Relatórios", async () => {
    const user = userEvent.setup();
    render(<DashboardView inicial={DADOS} podeCriarProva />);
    // Nenhum texto "Relatório(s)" no painel (o único acesso é o item de menu).
    expect(screen.queryByText(/relat[óo]rio/i)).toBeNull();
    // Clicar TODOS os botões nunca navega para /relatorios.
    for (const botao of screen.getAllByRole("button")) {
      await user.click(botao);
    }
    for (const chamada of nav.push.mock.calls) {
      expect(String(chamada[0])).not.toMatch(/\/relatorios/);
    }
    // Os únicos atalhos continuam sendo Escanear (universal) e Nova Prova (3Studio).
    expect(screen.getByText("Escanear QR Code")).toBeInTheDocument();
    expect(screen.getByText("Nova Prova")).toBeInTheDocument();
  });

  it("sem SSR (inicial null): busca no cliente e renderiza", async () => {
    mocks.fetchDashboard.mockResolvedValue(DADOS);
    render(<DashboardView inicial={null} podeCriarProva />);
    await waitFor(() => expect(screen.getByLabelText("6894")).toBeInTheDocument());
    expect(mocks.fetchDashboard).toHaveBeenCalledTimes(1);
  });
});
