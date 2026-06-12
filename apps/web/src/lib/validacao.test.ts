import { describe, expect, it } from "vitest";

import { emailValido, senhaValida } from "./validacao";

describe("senhaValida (política RF-018 — espelho do backend)", () => {
  it.each(["abcdef12", "A1bcdefg", "12345678a"])("aceita '%s'", (senha) => {
    expect(senhaValida(senha)).toBe(true);
  });

  it.each([
    ["a1b2c3", "curta"],
    ["12345678", "sem letra"],
    ["abcdefgh", "sem número"],
    ["", "vazia"],
  ])("rejeita '%s' (%s)", (senha) => {
    expect(senhaValida(senha)).toBe(false);
  });
});

describe("emailValido", () => {
  it.each(["a@b.co", "mario.souza@estudioearte.com.br", "  x@y.zz  "])("aceita '%s'", (email) => {
    expect(emailValido(email)).toBe(true);
  });

  it.each(["nao-e-email", "a@b", "@x.y", "a b@c.de"])("rejeita '%s'", (email) => {
    expect(emailValido(email)).toBe(false);
  });
});
