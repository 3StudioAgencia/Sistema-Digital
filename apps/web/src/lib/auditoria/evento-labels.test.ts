import { describe, expect, it } from "vitest";

import {
  EVENTO_COR,
  EVENTO_LABELS,
  EVENTO_ORDEM,
  corEvento,
  rotuloEvento,
  type EventoAuditoria,
} from "./evento-labels";

const TODOS: EventoAuditoria[] = [
  "criou_prova",
  "escaneou_qr",
  "mudou_status",
  "aprovou_prova",
  "reprovou_prova",
  "reiniciou_ciclo",
  "cancelou_prova",
];

describe("evento-labels (W6-C20)", () => {
  it("tem rótulo e cor para os 7 tipos de evento", () => {
    for (const e of TODOS) {
      expect(EVENTO_LABELS[e]).toBeTruthy();
      expect(EVENTO_COR[e]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("a ordem cobre exatamente os 7 tipos, sem repetição", () => {
    expect(new Set(EVENTO_ORDEM)).toEqual(new Set(TODOS));
    expect(EVENTO_ORDEM).toHaveLength(7);
  });

  it("rotuloEvento cai no valor cru para evento desconhecido", () => {
    expect(rotuloEvento("criou_prova")).toBe("Criou prova");
    expect(rotuloEvento("xyz")).toBe("xyz");
  });

  it("corEvento devolve cinza neutro para evento desconhecido", () => {
    expect(corEvento("escaneou_qr")).toBe(EVENTO_COR.escaneou_qr);
    expect(corEvento("xyz")).toBe("#9ca3af");
  });
});
