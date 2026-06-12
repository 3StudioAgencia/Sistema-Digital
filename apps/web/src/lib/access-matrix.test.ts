import { describe, expect, it } from "vitest";

import {
  type Perfil,
  type Recurso,
  RECURSOS_ADMIN,
  RECURSOS_UNIVERSAIS,
  can,
  perfilDeClaims,
  podeAcessarRota,
  recursoDaRota,
} from "./access-matrix";

const ADMIN: Perfil = { setor: "studio", administrador: true };
const VENDEDOR: Perfil = { setor: "vendedor", administrador: false };
const MOTORISTA: Perfil = { setor: "motorista", administrador: false };
// Ortogonalidade (ADR-023): um Vendedor pode ser Admin.
const VENDEDOR_ADMIN: Perfil = { setor: "vendedor", administrador: true };

const TODOS_RECURSOS: Recurso[] = [...RECURSOS_ADMIN, ...RECURSOS_UNIVERSAIS];

describe("access-matrix · can (Matriz §7 / ADR-023)", () => {
  it("admin acessa todos os recursos", () => {
    for (const recurso of TODOS_RECURSOS) {
      expect(can(ADMIN, recurso)).toBe(true);
    }
  });

  it("não-admin acessa só os universais; nega os exclusivos de admin", () => {
    for (const recurso of RECURSOS_UNIVERSAIS) {
      expect(can(VENDEDOR, recurso)).toBe(true);
    }
    for (const recurso of RECURSOS_ADMIN) {
      expect(can(VENDEDOR, recurso)).toBe(false);
      expect(can(MOTORISTA, recurso)).toBe(false);
    }
  });

  it("recurso de admin chaveia pelo FLAG, não pelo setor (Vendedor-Admin acessa)", () => {
    for (const recurso of RECURSOS_ADMIN) {
      expect(can(VENDEDOR_ADMIN, recurso)).toBe(true);
    }
  });
});

describe("access-matrix · recursoDaRota", () => {
  it.each([
    ["/dashboard", "dashboard"],
    ["/escanear", "escanear"],
    ["/provas", "provas"],
    ["/provas/PRV-2026-06-ABC123", "provas"],
    ["/provas/nova", "criar_prova"],
    ["/usuarios", "cadastro_usuarios"],
    ["/usuarios/123", "cadastro_usuarios"],
    ["/relatorios", "relatorios"],
    ["/configuracoes", "configuracoes"],
    ["/auditoria", "log_auditoria"],
  ])("%s → %s", (rota, recurso) => {
    expect(recursoDaRota(rota)).toBe(recurso);
  });

  it.each(["/informacoes", "/", "/qualquer-coisa"])("%s é rota neutra (null)", (rota) => {
    expect(recursoDaRota(rota)).toBeNull();
  });
});

describe("access-matrix · podeAcessarRota", () => {
  it("não-admin: universais e neutras liberadas; páginas de admin negadas", () => {
    for (const rota of ["/dashboard", "/escanear", "/provas", "/provas/X", "/informacoes"]) {
      expect(podeAcessarRota(VENDEDOR, rota)).toBe(true);
    }
    for (const rota of [
      "/usuarios",
      "/provas/nova",
      "/relatorios",
      "/configuracoes",
      "/auditoria",
    ]) {
      expect(podeAcessarRota(VENDEDOR, rota)).toBe(false);
    }
  });

  it("admin acessa qualquer rota da Matriz", () => {
    for (const rota of [
      "/dashboard",
      "/provas/nova",
      "/usuarios",
      "/relatorios",
      "/configuracoes",
    ]) {
      expect(podeAcessarRota(ADMIN, rota)).toBe(true);
    }
  });
});

describe("access-matrix · perfilDeClaims", () => {
  it("eleva setor/administrador dos claims", () => {
    expect(perfilDeClaims({ setor: "studio", administrador: true })).toEqual({
      setor: "studio",
      administrador: true,
    });
    expect(perfilDeClaims({ setor: "vendedor", administrador: false })).toEqual({
      setor: "vendedor",
      administrador: false,
    });
  });

  it("nega por padrão: sem claims, sem flag, ou flag não-booleano", () => {
    expect(perfilDeClaims(null)).toEqual({ setor: null, administrador: false });
    expect(perfilDeClaims({ setor: "studio" })).toEqual({ setor: "studio", administrador: false });
    // String "true" NÃO concede (o hook emite boolean; estrito por segurança).
    expect(perfilDeClaims({ setor: "studio", administrador: "true" }).administrador).toBe(false);
  });
});
