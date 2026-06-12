import { describe, expect, it } from "vitest";

import { NAV_PRINCIPAL, NAV_SECUNDARIA, hrefAtivo } from "./nav-items";

describe("nav-items (DP-6)", () => {
  it("mantém a ordem do design", () => {
    expect(NAV_PRINCIPAL.map((i) => i.rotulo)).toEqual([
      "Dashboard",
      "Provas",
      "Nova prova",
      "Escanear",
      "Relatórios",
      "Usuários",
    ]);
    expect(NAV_SECUNDARIA.map((i) => i.rotulo)).toEqual(["Configurações", "Informações"]);
  });

  it("resolve o ativo por prefixo mais longo (/provas/nova ≠ /provas)", () => {
    expect(hrefAtivo("/provas")).toBe("/provas");
    expect(hrefAtivo("/provas/nova")).toBe("/provas/nova");
    expect(hrefAtivo("/provas/PRV-2026-06-ABC123")).toBe("/provas");
    expect(hrefAtivo("/usuarios")).toBe("/usuarios");
    expect(hrefAtivo("/rota-desconhecida")).toBeNull();
  });
});
