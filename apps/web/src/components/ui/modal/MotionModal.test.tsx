import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MotionModal } from "./MotionModal";

/** Ativa prefers-reduced-motion: animações instantâneas → testes determinísticos. */
function mockReducedMotion(reduce: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: reduce && query.includes("prefers-reduced-motion"),
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
  mockReducedMotion(true);
});

function Harness({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <MotionModal open={open} onClose={onClose} labelledBy="t">
      <h2 id="t">Título do modal</h2>
      <button type="button">Ação</button>
    </MotionModal>
  );
}

describe("MotionModal (DP-8 / DAT §5.2)", () => {
  it("renderiza como dialog acessível quando aberto", () => {
    render(<Harness open={true} onClose={() => {}} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby", "t");
    expect(screen.getByText("Título do modal")).toBeInTheDocument();
  });

  it("não renderiza nada quando fechado", () => {
    render(<Harness open={false} onClose={() => {}} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("fecha com ESC", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<Harness open={true} onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("fecha ao clicar no overlay, mas NÃO ao clicar no painel", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<Harness open={true} onClose={onClose} />);
    await user.click(screen.getByText("Título do modal"));
    expect(onClose).not.toHaveBeenCalled();
    await user.click(screen.getByTestId("modal-overlay"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("trava o scroll do body enquanto aberto e libera ao fechar", async () => {
    const { rerender } = render(<Harness open={true} onClose={() => {}} />);
    expect(document.body.style.overflow).toBe("hidden");
    rerender(<Harness open={false} onClose={() => {}} />);
    await waitFor(() => expect(document.body.style.overflow).toBe(""));
  });
});
