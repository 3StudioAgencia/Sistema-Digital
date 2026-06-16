import { describe, expect, it } from "vitest";

import {
  mascararCodigo,
  mascararResto,
  montarCodigo,
  normalizarCodigo,
  validarCodigo,
} from "./codigo";

describe("codigo (W3-C10) — espelho do formato do C06 (DP-1)", () => {
  it("valida o formato canônico PRV-AAAA-MM-NNNNNN (e normaliza antes)", () => {
    expect(validarCodigo("PRV-2026-06-A2KMQ9")).toBe(true);
    expect(validarCodigo("prv-2026-06-a2kmq9")).toBe(true); // minúsculas → normaliza
    expect(validarCodigo("  PRV-2026-06-A2KMQ9 \n")).toBe(true); // espaço/quebra do QR
  });

  it("rejeita formato/charset inválidos (inclusive a máscara legada do design)", () => {
    expect(validarCodigo("3S-1234-5678")).toBe(false); // "3S-/8 dígitos" do mockup
    expect(validarCodigo("PRV-2026-13-A2KMQ9")).toBe(false); // mês fora de 01..12
    expect(validarCodigo("PRV-2026-06-A2KMQ0")).toBe(false); // 0 ambíguo (fora do alfabeto)
    expect(validarCodigo("PRV-2026-06-A2KMQ")).toBe(false); // sufixo curto
  });

  it("normaliza como o servidor (trim + MAIÚSCULAS, idempotente)", () => {
    expect(normalizarCodigo("  prv-2026-06-a2kmq9\n")).toBe("PRV-2026-06-A2KMQ9");
    expect(normalizarCodigo("PRV-2026-06-A2KMQ9")).toBe("PRV-2026-06-A2KMQ9");
  });

  it("mascara a parte editável em AAAA-MM-XXXXXX", () => {
    expect(mascararResto("20260")).toBe("2026-0");
    expect(mascararResto("202606A2KMQ9")).toBe("2026-06-A2KMQ9");
    expect(mascararResto("2026-06-a2kmq9")).toBe("2026-06-A2KMQ9"); // recoloca hífens + maiúsculas
    expect(mascararResto("PRV-2026-06-A2KMQ9")).toBe("2026-06-A2KMQ9"); // colou o código inteiro
    expect(mascararResto("2026-06-A2KMQ9EXTRA")).toBe("2026-06-A2KMQ9"); // trunca em 12
  });

  it("montarCodigo recompõe com o prefixo fixo e bate com o formato canônico", () => {
    expect(montarCodigo("2026-06-A2KMQ9")).toBe("PRV-2026-06-A2KMQ9");
    expect(validarCodigo(montarCodigo(mascararResto("prv2026 06 a2kmq9")))).toBe(true);
  });

  it("mascararCodigo monta o código INTEIRO PRV-AAAA-MM-XXXXXX posicionalmente", () => {
    expect(mascararCodigo("")).toBe(""); // vazio → mostra o placeholder
    expect(mascararCodigo("PRV")).toBe("PRV");
    expect(mascararCodigo("PRV2")).toBe("PRV-2");
    expect(mascararCodigo("prv-2026-06-a2kmq9")).toBe("PRV-2026-06-A2KMQ9"); // colar minúsculas
    expect(mascararCodigo("PRV202606A2KMQ9")).toBe("PRV-2026-06-A2KMQ9"); // sem hífens
    expect(mascararCodigo("PRV202606A2KMQ9EXTRA")).toBe("PRV-2026-06-A2KMQ9"); // trunca em 15
    expect(validarCodigo(mascararCodigo("prv202606a2kmq9"))).toBe(true);
  });
});
