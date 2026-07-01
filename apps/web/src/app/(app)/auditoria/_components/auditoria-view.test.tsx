import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RegistroAuditoria } from "../../../../lib/api/auditoria";

const nav = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => "/auditoria",
  useSearchParams: () => new URLSearchParams(),
}));

const api = vi.hoisted(() => ({
  listarAuditoria: vi.fn(),
  listarAtoresAuditoria: vi.fn(),
  verificarIntegridadeAuditoria: vi.fn(),
}));
vi.mock("@/lib/api/auditoria", () => api);

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("@/components/ui/toast/ToastProvider", () => ({ useToast: () => toast }));

import { AuditoriaView } from "./auditoria-view";

function registro(over: Partial<RegistroAuditoria>): RegistroAuditoria {
  return {
    id: "r1",
    seq: 1,
    evento: "mudou_status",
    ator_id: "a1",
    ator_nome: "Renan Petrim",
    ator_setor: "vendedor",
    prova_id: "p1",
    prova_codigo: "PRV-2026-06-A2KMQ9",
    prova_cliente: "Cafe",
    prova_requerimento: "155295",
    acao: "identificar_e_assinar",
    estado_origem: "criada",
    estado_destino: "retirada_vendedor",
    ciclo: 1,
    motivo: null,
    ip: "203.0.113.7",
    origem: "Aplicação Web · Chrome",
    created_at: "2026-06-19T13:50:30.000Z",
    hash: "538453d75fb3ab5691a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5061",
    ...over,
  };
}

const ITENS = [
  registro({ id: "r2", seq: 2, evento: "mudou_status", ator_nome: "Renan Petrim" }),
  registro({
    id: "r1",
    seq: 1,
    evento: "criou_prova",
    ator_nome: "Mônica",
    ator_setor: "studio",
    acao: null,
    estado_origem: null,
    estado_destino: null,
  }),
];

beforeEach(() => {
  vi.clearAllMocks();
  api.listarAuditoria.mockResolvedValue({ items: ITENS, total: 2, page: 1, page_size: 50 });
  api.listarAtoresAuditoria.mockResolvedValue([
    { id: "a1", nome: "Renan Petrim" },
    { id: "a2", nome: "Mônica" },
  ]);
  api.verificarIntegridadeAuditoria.mockResolvedValue({ intacto: true, total: 2, quebrou_em: null });
});

afterEach(() => vi.useRealTimers());

describe("AuditoriaView (W6-C20)", () => {
  it("renderiza cabeçalho + subtítulo do design", async () => {
    render(<AuditoriaView />);
    expect(screen.getByRole("heading", { name: "Auditoria", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Log imutável de todas as ações do sistema")).toBeInTheDocument();
  });

  it("lista os eventos (color-coding por tipo) e abre o detalhe do 1º (master-detail)", async () => {
    render(<AuditoriaView />);
    // Lista: ambos os eventos aparecem.
    expect(await screen.findByRole("button", { name: /Criou prova/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Mudou status/ })).toBeInTheDocument();
    // Detalhe default = 1º item (recentes): "Mudou status" por Renan.
    expect(screen.getByRole("heading", { name: "Mudou status", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Registrado por Renan Petrim")).toBeInTheDocument();
    // Rodapé de integridade com o hash do chain.
    expect(screen.getByText("Registro íntegro e imutável")).toBeInTheDocument();
    expect(screen.getByText(/^sha256:538453d75fb3ab5691/)).toBeInTheDocument();
  });

  it("selecionar outro evento troca o painel de detalhe", async () => {
    const user = userEvent.setup();
    render(<AuditoriaView />);
    await user.click(await screen.findByRole("button", { name: /Criou prova/ }));
    expect(screen.getByRole("heading", { name: "Criou prova", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Registrado por Mônica")).toBeInTheDocument();
  });

  it("preset de período escreve De/Até na URL (estado de filtro — reusa C07)", async () => {
    const user = userEvent.setup();
    render(<AuditoriaView />);
    await user.click(screen.getByRole("button", { name: "30d" }));
    expect(nav.replace).toHaveBeenCalledWith(
      expect.stringMatching(/de=\d{4}-\d{2}-\d{2}&ate=\d{4}-\d{2}-\d{2}/),
      { scroll: false },
    );
  });

  it("verificar integridade chama o backend e dá feedback (read-only — DP-4)", async () => {
    const user = userEvent.setup();
    render(<AuditoriaView />);
    await user.click(screen.getByRole("button", { name: /Verificar integridade/ }));
    await waitFor(() => expect(api.verificarIntegridadeAuditoria).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalled();
  });
});
