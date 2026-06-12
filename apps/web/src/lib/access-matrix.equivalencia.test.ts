/**
 * Harness de equivalência (lado web) — W1-C05.
 *
 * Trava `access-matrix.ts` à Matriz canônica (`access-matrix.cells.json`). O
 * lado api (`apps/api/tests/unit/test_equivalencia_matriz.py`) trava `rbac.py`
 * ao MESMO arquivo — logo as duas linguagens concordam por construção (regra do
 * PR único — DAT §7.3).
 */
import { describe, expect, it } from "vitest";

import { type Perfil, type Recurso, RECURSOS_ADMIN, RECURSOS_UNIVERSAIS, can } from "./access-matrix";
import cells from "./access-matrix.cells.json";

const ADMIN: Perfil = { setor: "studio", administrador: true };
const NAO_ADMIN: Perfil = { setor: "vendedor", administrador: false };

const celulas = cells.celulas as Record<string, "todos" | "admin">;

describe("Equivalência: access-matrix.ts ⇔ Matriz canônica", () => {
  it("o conjunto de recursos implementado == o da Matriz canônica", () => {
    const implementados = new Set<string>([...RECURSOS_ADMIN, ...RECURSOS_UNIVERSAIS]);
    expect(implementados).toEqual(new Set(Object.keys(celulas)));
  });

  it("admin/universais são partição disjunta de todos os recursos", () => {
    for (const r of RECURSOS_ADMIN) expect(RECURSOS_UNIVERSAIS.has(r)).toBe(false);
  });

  it("can() concorda com a Matriz canônica em TODAS as células", () => {
    for (const [recurso, politica] of Object.entries(celulas)) {
      const r = recurso as Recurso;
      expect(can(ADMIN, r)).toBe(true); // admin (flag) acessa tudo
      expect(can(NAO_ADMIN, r)).toBe(politica === "todos");
    }
  });
});
