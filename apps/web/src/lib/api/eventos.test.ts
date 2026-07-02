import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { assinarDashboard } from "./eventos";

// jsdom não implementa EventSource — stub controlável (registra instâncias e
// permite emitir eventos manualmente).
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  readonly withCredentials: boolean;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  closed = false;
  private readonly listeners: Record<string, Array<(ev: MessageEvent) => void>> = {};

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = init?.withCredentials ?? false;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (ev: MessageEvent) => void): void {
    (this.listeners[type] ??= []).push(cb);
  }

  emit(type: string): void {
    if (type === "message") this.onmessage?.(new MessageEvent("message"));
    else for (const cb of this.listeners[type] ?? []) cb(new MessageEvent(type));
  }

  close(): void {
    this.closed = true;
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("assinarDashboard (stream SSE do dashboard — etapa 3)", () => {
  it("abre o stream same-origin com credenciais (cookie httpOnly)", () => {
    assinarDashboard({ onMudou: vi.fn(), onExpira: vi.fn() });
    const es = FakeEventSource.instances[0];
    expect(es.url).toBe("/api/dashboard/stream");
    expect(es.withCredentials).toBe(true);
  });

  it("dispara onMudou no message ('mudou') e no evento 'conectado'", () => {
    const onMudou = vi.fn();
    assinarDashboard({ onMudou, onExpira: vi.fn() });
    const es = FakeEventSource.instances[0];
    es.emit("message");
    es.emit("conectado");
    expect(onMudou).toHaveBeenCalledTimes(2);
  });

  it("dispara onExpira no evento 'expira'", () => {
    const onExpira = vi.fn();
    assinarDashboard({ onMudou: vi.fn(), onExpira });
    FakeEventSource.instances[0].emit("expira");
    expect(onExpira).toHaveBeenCalledTimes(1);
  });

  it("o cleanup fecha o EventSource", () => {
    const cleanup = assinarDashboard({ onMudou: vi.fn(), onExpira: vi.fn() });
    const es = FakeEventSource.instances[0];
    cleanup();
    expect(es.closed).toBe(true);
  });

  it("degrada para no-op quando não há EventSource (SSR/sem stub)", () => {
    vi.stubGlobal("EventSource", undefined);
    const cleanup = assinarDashboard({ onMudou: vi.fn(), onExpira: vi.fn() });
    expect(() => cleanup()).not.toThrow();
  });
});
