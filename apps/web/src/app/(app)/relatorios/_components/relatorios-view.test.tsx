import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RelatorioGeral } from "../../../../lib/api/relatorios";

// Router espionado (aba/filtros vão para a URL via replace).
const nav = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => "/relatorios",
  // searchParams vazio → aba "geral", sem filtros.
  useSearchParams: () => new URLSearchParams(),
}));

// API mockada — valida que só a aba ATIVA busca (lazy — DP-6).
const api = vi.hoisted(() => ({
  fetchRelatorioGeral: vi.fn(),
  fetchRelatorioStudio: vi.fn(),
  fetchRelatorioVendedores: vi.fn(),
  fetchRelatorioClicheria: vi.fn(),
  exportarRelatorioCsv: vi.fn(),
  listarVendedores: vi.fn(),
  rotasDoGrupo: () => [],
}));
vi.mock("@/lib/api/relatorios", () => api);

// Gráficos fora do teste (Recharts precisa de layout/ResizeObserver — jsdom não tem).
vi.mock("./charts", () => ({
  VolumeBars: () => null,
  ProvasAtivasDonut: () => <div data-testid="donut" />,
}));

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("@/components/ui/toast/ToastProvider", () => ({ useToast: () => toast }));

import { RelatoriosView } from "./relatorios-view";

const GERAL: RelatorioGeral = {
  total_geral: 20,
  volume: [],
  tempo_medio_aprovacao_horas: 10,
  taxa_reprovacao: 8,
  distribuicao_rota: [
    { rota: "matriz", total: 12 },
    { rota: "lam_matriz", total: 4 },
    { rota: "filial", total: 3 },
    { rota: "lam_filial", total: 1 },
  ],
  ativas_aguardando_vendedor: 5,
  ativas_reprovadas: 2,
  metricas_por_vendedor: [
    {
      vendedor_id: "v1",
      vendedor_nome: "Mário Souza",
      localizacao: "filial",
      volume: 12,
      aprovadas: 10,
      reprovadas: 1,
      taxa_reprovacao: 9.1,
      tempo_medio_horas: 10,
      atrasadas: 2,
    },
  ],
  provas_atrasadas: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listarVendedores.mockResolvedValue([]);
  api.fetchRelatorioGeral.mockResolvedValue(GERAL);
  api.exportarRelatorioCsv.mockResolvedValue(undefined);
});

afterEach(() => vi.useRealTimers());

describe("RelatoriosView (W5-C17)", () => {
  it("renderiza cabeçalho, 4 abas e Exportar CSV", async () => {
    render(<RelatoriosView />);
    expect(screen.getByRole("heading", { name: "Relatórios" })).toBeInTheDocument();
    for (const t of ["Geral", "3Studio", "Vendedores", "Clicheria"]) {
      expect(screen.getByRole("tab", { name: t })).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: /Exportar CSV/ })).toBeInTheDocument();
  });

  it("aba Geral é a ativa e busca SÓ a sua agregação (lazy — DP-6)", async () => {
    render(<RelatoriosView />);
    await waitFor(() => expect(screen.getByText("Total geral")).toBeInTheDocument());
    expect(api.fetchRelatorioGeral).toHaveBeenCalledTimes(1);
    // As demais abas NÃO buscam (não estão montadas).
    expect(api.fetchRelatorioStudio).not.toHaveBeenCalled();
    expect(api.fetchRelatorioVendedores).not.toHaveBeenCalled();
    expect(api.fetchRelatorioClicheria).not.toHaveBeenCalled();
    // Número via aria-label do AnimatedCounter.
    expect(screen.getByLabelText("20")).toBeInTheDocument();
  });

  it("clicar numa aba escreve ?aba= na URL (estado compartilhado — DP-4)", async () => {
    const user = userEvent.setup();
    render(<RelatoriosView />);
    await user.click(screen.getByRole("tab", { name: "3Studio" }));
    expect(nav.replace).toHaveBeenCalledWith("/relatorios?aba=studio", { scroll: false });
  });

  it("Exportar CSV abre o menu e dispara o download da aba escolhida (DP-5)", async () => {
    const user = userEvent.setup();
    render(<RelatoriosView />);
    await user.click(screen.getByRole("button", { name: /Exportar CSV/ }));
    await user.click(screen.getByRole("menuitem", { name: /Exportar .Vendedores/ }));
    expect(api.exportarRelatorioCsv).toHaveBeenCalledWith("vendedores", expect.any(Object));
  });

  it("preset de período escreve De/Até na URL", async () => {
    const user = userEvent.setup();
    render(<RelatoriosView />);
    await user.click(screen.getByRole("button", { name: "30d" }));
    expect(nav.replace).toHaveBeenCalledWith(
      expect.stringMatching(/de=\d{4}-\d{2}-\d{2}&ate=\d{4}-\d{2}-\d{2}/),
      { scroll: false },
    );
  });
});
