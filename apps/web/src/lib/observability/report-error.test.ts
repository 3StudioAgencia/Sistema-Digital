import { afterEach, describe, expect, it, vi } from "vitest";

import { reportClientError } from "./report-error";

describe("reportClientError", () => {
  afterEach(() => vi.restoreAllMocks());

  it("emite um console.error estruturado com boundary, digest e erro", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const erro = new Error("boom");

    reportClientError(erro, { boundary: "app", digest: "abc123" });

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith("[client-error]", {
      boundary: "app",
      digest: "abc123",
      error: erro,
    });
  });

  it("normaliza boundary/digest ausentes para null", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    reportClientError("falha em string");

    expect(spy).toHaveBeenCalledWith("[client-error]", {
      boundary: null,
      digest: null,
      error: "falha em string",
    });
  });
});
