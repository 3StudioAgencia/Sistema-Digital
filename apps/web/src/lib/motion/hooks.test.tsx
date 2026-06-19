import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { setReducedMotion } from "@/test/motion";

import { useReducedMotion } from "./hooks";

describe("useReducedMotion", () => {
  it("retorna false quando o usuário não pede redução de movimento", () => {
    setReducedMotion(false);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  it("retorna true com prefers-reduced-motion: reduce (animações → instantâneas)", () => {
    setReducedMotion(true);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });
});
