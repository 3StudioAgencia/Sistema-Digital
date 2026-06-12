import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Usuario } from "@/lib/api/usuarios";

const mocks = vi.hoisted(() => ({
  pathname: { value: "/usuarios" },
  replace: vi.fn(),
  refresh: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname.value,
  useRouter: () => ({ replace: mocks.replace, refresh: mocks.refresh, push: vi.fn() }),
}));

vi.mock("@/lib/supabase/client", () => ({
  getSupabaseBrowserClient: () => ({ auth: { signOut: mocks.signOut } }),
}));

import { Sidebar } from "./Sidebar";

const MONICA: Usuario = {
  id: "u1",
  nome: "Mônica Andrade",
  email: "monica@3studio.test",
  setor: "studio",
  localizacao: null,
  administrador: true,
  ativo: true,
  created_at: null,
  updated_at: null,
};

const ANA_VENDEDORA: Usuario = {
  id: "u2",
  nome: "Ana Lima",
  email: "ana@x.y",
  setor: "vendedor",
  localizacao: "matriz",
  administrador: false,
  ativo: true,
  created_at: null,
  updated_at: null,
};

beforeEach(() => {
  mocks.pathname.value = "/usuarios";
  mocks.replace.mockClear();
  mocks.signOut.mockReset().mockResolvedValue({ error: null });
});

describe("Sidebar (app shell — W1-C04)", () => {
  it("renderiza wordmark, saudação, busca inerte e itens na ordem do design", () => {
    render(<Sidebar usuario={MONICA} emailSessao="monica@3studio.test" />);

    expect(screen.getByAltText("3Studio")).toBeInTheDocument();
    expect(screen.getByText("Olá Mônica!")).toBeInTheDocument();
    expect(screen.getByLabelText(/buscar/i)).toBeDisabled();

    const nav = screen.getByRole("navigation", { name: "Navegação principal" });
    const rotulos = within(nav)
      .getAllByRole("link")
      .map((l) => l.textContent);
    expect(rotulos).toEqual([
      "Dashboard",
      "Provas",
      "Nova prova",
      "Escanear",
      "Relatórios",
      "Usuários",
      "Configurações",
      "Informações",
    ]);
  });

  it("filtra o menu por perfil: não-admin não vê páginas exclusivas de 3Studio (W1-C05)", () => {
    mocks.pathname.value = "/dashboard";
    render(<Sidebar usuario={ANA_VENDEDORA} emailSessao="ana@x.y" />);

    const nav = screen.getByRole("navigation", { name: "Navegação principal" });
    const rotulos = within(nav)
      .getAllByRole("link")
      .map((l) => l.textContent);
    // Só universais (Dashboard/Provas/Escanear) + neutra (Informações).
    expect(rotulos).toEqual(["Dashboard", "Provas", "Escanear", "Informações"]);
    // Exclusivos de admin ausentes:
    expect(within(nav).queryByText("Nova prova")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Usuários")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Relatórios")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Configurações")).not.toBeInTheDocument();
  });

  it("marca o item ativo conforme a rota (aria-current)", () => {
    render(<Sidebar usuario={MONICA} emailSessao="monica@3studio.test" />);
    expect(screen.getByRole("link", { name: /usuários/i })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /dashboard/i })).not.toHaveAttribute("aria-current");
  });

  it("rodapé mostra nome, setor e avatar com a inicial", () => {
    render(<Sidebar usuario={MONICA} emailSessao="monica@3studio.test" />);
    expect(screen.getAllByText("Mônica").length).toBeGreaterThanOrEqual(1); // rodapé
    expect(screen.getByText("3Studio", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("M")).toBeInTheDocument(); // inicial no avatar
  });

  it("degrada para o e-mail da sessão quando não há linha de domínio", () => {
    render(<Sidebar usuario={null} emailSessao="fulano.tal@empresa.com" />);
    expect(screen.getByText("Olá fulano.tal!")).toBeInTheDocument();
  });

  it("Sair faz signOut e volta ao login", async () => {
    const user = userEvent.setup();
    render(<Sidebar usuario={MONICA} emailSessao="monica@3studio.test" />);
    await user.click(screen.getByRole("button", { name: "Sair" }));
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
    expect(mocks.replace).toHaveBeenCalledWith("/login");
  });
});
