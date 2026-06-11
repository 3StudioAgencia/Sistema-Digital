import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace, refresh: mocks.refresh }),
}));

vi.mock("@/lib/supabase/client", () => ({
  getSupabaseBrowserClient: () => ({ auth: { signOut: mocks.signOut } }),
}));

import { InactivityGuard } from "./inactivity-guard";

describe("InactivityGuard (RNF-004 / DP-3)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mocks.replace.mockClear();
    mocks.refresh.mockClear();
    mocks.signOut.mockReset();
    mocks.signOut.mockResolvedValue({ error: null });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("após o tempo ocioso faz signOut e volta ao login com ?expirado=1", async () => {
    render(<InactivityGuard timeoutMs={1000} />);
    await vi.advanceTimersByTimeAsync(1000);
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
    expect(mocks.replace).toHaveBeenCalledWith("/login?expirado=1");
  });

  it("uma interação reinicia o timer (não expira antes do intervalo)", async () => {
    render(<InactivityGuard timeoutMs={1000} />);
    await vi.advanceTimersByTimeAsync(600);
    window.dispatchEvent(new Event("mousemove")); // reinicia
    await vi.advanceTimersByTimeAsync(600); // 1200ms totais, mas resetou aos 600
    expect(mocks.signOut).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(500); // completa o novo ciclo
    expect(mocks.signOut).toHaveBeenCalledTimes(1);
  });
});
