import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  signInWithPassword: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, refresh: mocks.refresh }),
}));

vi.mock("@/lib/supabase/client", () => ({
  getSupabaseBrowserClient: () => ({ auth: { signInWithPassword: mocks.signInWithPassword } }),
}));

import { AuthFlow } from "./auth-flow";

beforeEach(() => {
  mocks.push.mockClear();
});

describe("AuthFlow (DP-7)", () => {
  it("renderiza boas-vindas e formulário (no mobile a CSS mostra as boas-vindas primeiro)", () => {
    render(<AuthFlow expired={false} />);
    expect(screen.getByRole("heading", { name: "Seja bem vindo!" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fazer login" })).toBeInTheDocument();

    // O CTA "Entrar" das boas-vindas vive na região própria (distinto do submit).
    const welcome = screen.getByRole("region", { name: "Boas-vindas" });
    expect(within(welcome).getByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("clicar em Entrar nas boas-vindas avança o passo sem quebrar o formulário", async () => {
    const user = userEvent.setup();
    render(<AuthFlow expired={false} />);
    const welcome = screen.getByRole("region", { name: "Boas-vindas" });
    await user.click(within(welcome).getByRole("button", { name: "Entrar" }));
    // O formulário continua disponível (no mobile, agora revelado).
    expect(screen.getByRole("heading", { name: "Fazer login" })).toBeInTheDocument();
    expect(screen.getByLabelText("E-mail:")).toBeInTheDocument();
  });
});
