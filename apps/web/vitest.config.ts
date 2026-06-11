import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Alias "@/..." → ./src/... (regex evita capturar "@supabase/..."). Explícito
// para que vi.mock("@/lib/...") resolva ao MESMO módulo que os componentes importam.
const srcDir = fileURLToPath(new URL("./src", import.meta.url));

// Testes de componente/unidade (RTL + jsdom). E2E é Playwright (pasta e2e/).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [{ find: /^@\//, replacement: `${srcDir}/` }],
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: true,
    restoreMocks: true,
  },
});
