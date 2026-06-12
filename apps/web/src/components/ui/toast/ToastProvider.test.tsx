import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "./ToastProvider";

function mockReducedMotion() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

beforeEach(() => {
  mockReducedMotion();
});

function Consumidor() {
  const toast = useToast();
  return (
    <>
      <button type="button" onClick={() => toast.success("Deu certo!")}>
        ok
      </button>
      <button type="button" onClick={() => toast.error("Deu errado!")}>
        erro
      </button>
    </>
  );
}

describe("ToastProvider (W1-C04)", () => {
  it("exibe toasts de sucesso e erro na região aria-live", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Consumidor />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "ok" }));
    await user.click(screen.getByRole("button", { name: "erro" }));
    expect(screen.getByText("Deu certo!")).toBeInTheDocument();
    expect(screen.getByText("Deu errado!")).toBeInTheDocument();
  });

  it("descarta ao clicar", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Consumidor />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "ok" }));
    await user.click(screen.getByText("Deu certo!"));
    await waitFor(() => expect(screen.queryByText("Deu certo!")).not.toBeInTheDocument());
  });

  it("auto-descarta após o tempo de leitura", async () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <Consumidor />
        </ToastProvider>,
      );
      act(() => {
        screen.getByRole("button", { name: "ok" }).click();
      });
      expect(screen.getByText("Deu certo!")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(4100);
      });
    } finally {
      vi.useRealTimers();
    }
    await waitFor(() => expect(screen.queryByText("Deu certo!")).not.toBeInTheDocument());
  });

  it("useToast fora do provider falha com mensagem clara", () => {
    expect(() => render(<Consumidor />)).toThrow(/ToastProvider/);
  });
});
