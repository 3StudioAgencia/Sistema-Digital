import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
}));

// Link → anchor simples (evita depender do contexto de router nos testes).
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { Welcome } from "./welcome";

function setViewport(matches: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => {
  mocks.replace.mockClear();
});

describe("Welcome (DP-7)", () => {
  it("mobile: mostra as boas-vindas e o Entrar leva ao /login", () => {
    setViewport(false);
    render(<Welcome />);
    expect(screen.getByText("Seja bem vindo!")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/login");
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("desktop (≥768px): encaminha direto para /login (boas-vindas é mobile-only)", () => {
    setViewport(true);
    render(<Welcome />);
    expect(mocks.replace).toHaveBeenCalledWith("/login");
  });
});
