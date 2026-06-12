import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  error: vi.fn(),
  pathname: { value: "/dashboard" },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname.value,
}));

vi.mock("@/components/ui/toast/ToastProvider", () => ({
  useToast: () => ({ error: mocks.error, success: vi.fn() }),
}));

import { RbacFlash } from "./rbac-flash";

describe("RbacFlash (toast de acesso negado — W1-C05 / DP-4)", () => {
  beforeEach(() => {
    mocks.error.mockClear();
    mocks.pathname.value = "/dashboard";
    document.cookie = "rbac_negado=; path=/; max-age=0";
  });

  afterEach(() => {
    document.cookie = "rbac_negado=; path=/; max-age=0";
  });

  it("dispara o toast e LIMPA o cookie quando o flash está presente", () => {
    document.cookie = "rbac_negado=1; path=/";
    render(<RbacFlash />);
    expect(mocks.error).toHaveBeenCalledTimes(1);
    expect(mocks.error).toHaveBeenCalledWith(expect.stringContaining("permissão"));
    // cookie consumido (one-shot): não há mais o flash
    expect(document.cookie).not.toContain("rbac_negado=1");
  });

  it("não dispara nada sem o flash", () => {
    render(<RbacFlash />);
    expect(mocks.error).not.toHaveBeenCalled();
  });
});
