import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  replace: vi.fn(),
  signInWithPassword: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, refresh: mocks.refresh, replace: mocks.replace }),
}));

vi.mock("@/lib/supabase/client", () => ({
  getSupabaseBrowserClient: () => ({ auth: { signInWithPassword: mocks.signInWithPassword } }),
}));

import { LoginPanel } from "./login-panel";

beforeEach(() => {
  mocks.push.mockClear();
  mocks.refresh.mockClear();
  mocks.signInWithPassword.mockReset();
});

describe("LoginPanel", () => {
  it("renderiza os elementos do design (telas de login)", () => {
    render(<LoginPanel expired={false} />);
    expect(screen.getByText("Fazer login")).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail:")).toBeInTheDocument();
    expect(screen.getByLabelText("Senha:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Esqueci minha senha" })).toBeInTheDocument();
    expect(screen.getByText("©3Studio 2026")).toBeInTheDocument();
    expect(screen.getByAltText("3Studio")).toBeInTheDocument();
  });

  it("exibe o aviso quando a sessão expirou por inatividade (?expirado=1)", () => {
    render(<LoginPanel expired={true} />);
    expect(screen.getByText(/sess[aã]o expirou por inatividade/i)).toBeInTheDocument();
  });

  it("login válido chama signInWithPassword e redireciona para o app shell", async () => {
    const user = userEvent.setup();
    mocks.signInWithPassword.mockResolvedValue({ error: null });
    render(<LoginPanel expired={false} />);

    await user.type(screen.getByLabelText("E-mail:"), "vendedor@3studio.test");
    await user.type(screen.getByLabelText("Senha:"), "minhaSenhaForte");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(mocks.signInWithPassword).toHaveBeenCalledWith({
      email: "vendedor@3studio.test",
      password: "minhaSenhaForte",
    });
    expect(mocks.push).toHaveBeenCalledWith("/usuarios");
  });

  it("login inválido mostra mensagem GENÉRICA, sem revelar o campo nem o detalhe do provedor", async () => {
    const user = userEvent.setup();
    mocks.signInWithPassword.mockResolvedValue({
      error: { message: "Invalid login credentials" },
    });
    render(<LoginPanel expired={false} />);

    await user.type(screen.getByLabelText("E-mail:"), "vendedor@3studio.test");
    await user.type(screen.getByLabelText("Senha:"), "errada");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/e-mail ou senha inv[aá]lidos/i);
    expect(alert.textContent ?? "").not.toContain("credentials");
    expect(mocks.push).not.toHaveBeenCalled();
  });

  it("'Esqueci minha senha' é inerte nesta wave e apenas exibe uma dica (DP-5)", async () => {
    const user = userEvent.setup();
    render(<LoginPanel expired={false} />);
    await user.click(screen.getByRole("button", { name: "Esqueci minha senha" }));
    expect(screen.getByText(/fale com o administrador/i)).toBeInTheDocument();
  });
});
