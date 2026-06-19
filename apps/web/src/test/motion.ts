import { vi } from "vitest";

/**
 * Helper de teste da camada de animações (W6-C19) — centraliza o mock de
 * `window.matchMedia` que estava duplicado inline em vários testes.
 *
 * jsdom não implementa matchMedia (base do `useReducedMotion`). Esta função é
 * QUERY-AWARE: só casa a media query de redução de movimento; demais queries
 * retornam `matches: false`. Mantém o padrão `writable: true` usado no
 * vitest.setup (não declarar `configurable` — a propriedade já existe lá).
 *
 * Uso: `setReducedMotion(true)` em beforeEach para tornar animações
 * instantâneas e determinísticas; `setReducedMotion(false)` para o caminho com
 * movimento.
 */
export function setReducedMotion(reduce: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: reduce && query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}
