import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HOME_PADRAO } from "../../lib/access-matrix";

const mocks = vi.hoisted(() => {
  class CredenciaisInvalidasError extends Error {}
  return {
    push: vi.fn(),
    refresh: vi.fn(),
    replace: vi.fn(),
    login: vi.fn(),
    CredenciaisInvalidasError,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, refresh: mocks.refresh, replace: mocks.replace }),
}));

vi.mock("@/lib/auth/client", () => ({
  login: mocks.login,
  CredenciaisInvalidasError: mocks.CredenciaisInvalidasError,
}));

import { LoginPanel } from "./login-panel";

beforeEach(() => {
  mocks.push.mockClear();
  mocks.refresh.mockClear();
  mocks.login.mockReset();
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

  it("login válido chama o backend (login) e redireciona para a home do perfil", async () => {
    const user = userEvent.setup();
    mocks.login.mockResolvedValue({
      id: "u1",
      email: "vendedor@3studio.test",
      setor: "vendedor",
      administrador: false,
    });
    render(<LoginPanel expired={false} />);

    await user.type(screen.getByLabelText("E-mail:"), "vendedor@3studio.test");
    await user.type(screen.getByLabelText("Senha:"), "minhaSenhaForte");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(mocks.login).toHaveBeenCalledWith("vendedor@3studio.test", "minhaSenhaForte");
    // HOME_PADRAO (/dashboard) é universal: um vendedor NÃO é barrado pelo proxy.
    expect(mocks.push).toHaveBeenCalledWith(HOME_PADRAO);
  });

  it("login inválido mostra mensagem GENÉRICA, sem revelar o campo", async () => {
    const user = userEvent.setup();
    mocks.login.mockRejectedValue(new mocks.CredenciaisInvalidasError());
    render(<LoginPanel expired={false} />);

    await user.type(screen.getByLabelText("E-mail:"), "vendedor@3studio.test");
    await user.type(screen.getByLabelText("Senha:"), "errada");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/e-mail ou senha inv[aá]lidos/i);
    expect(mocks.push).not.toHaveBeenCalled();
  });

  it("'Esqueci minha senha' é inerte nesta wave e apenas exibe uma dica (DP-5)", async () => {
    const user = userEvent.setup();
    render(<LoginPanel expired={false} />);
    await user.click(screen.getByRole("button", { name: "Esqueci minha senha" }));
    expect(screen.getByText(/fale com o administrador/i)).toBeInTheDocument();
  });
});
