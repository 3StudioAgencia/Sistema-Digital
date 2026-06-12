import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ report: vi.fn() }));

vi.mock("@/lib/observability/report-error", () => ({
  reportClientError: mocks.report,
}));

import AppError from "./error";

beforeEach(() => mocks.report.mockClear());

describe("(app)/error — boundary do grupo autenticado", () => {
  it("renderiza alerta contextual e reporta o erro no mount", () => {
    const erro = Object.assign(new Error("boom"), { digest: "d-1" });

    render(<AppError error={erro} reset={() => {}} />);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Algo deu errado")).toBeInTheDocument();
    expect(screen.getByText(/navegue para outra seção pelo menu/i)).toBeInTheDocument();
    expect(screen.getByText("Referência: d-1")).toBeInTheDocument();
    expect(mocks.report).toHaveBeenCalledWith(erro, { boundary: "app", digest: "d-1" });
  });

  it("o botão Tentar novamente chama reset()", async () => {
    const user = userEvent.setup();
    const reset = vi.fn();

    render(<AppError error={new Error("x")} reset={reset} />);
    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("sem digest não mostra a linha de referência", () => {
    render(<AppError error={new Error("x")} reset={() => {}} />);
    expect(screen.queryByText(/Referência:/)).not.toBeInTheDocument();
  });
});
