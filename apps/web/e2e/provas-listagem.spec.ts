import { expect, test } from "@playwright/test";

const DESKTOP = { width: 1440, height: 900 };

/**
 * Listagem de provas (W2-C07).
 *
 * Sem credenciais: valida a PROTEÇÃO da rota (a página é universal, mas exige
 * autenticação — redirect → /login), inclusive a rota de detalhe `/provas/{id}`.
 * Com E2E_LIVE=1 (sessão real + API + provas semeadas): tabela fiel ao design,
 * filtros sincronizados na URL (DP-5) e o "Ver" navegando ao detalhe (DP-6).
 * O ESCOPO por perfil (vendedor vê só as suas etc.) é coberto à exaustão no
 * nível de integração do backend (test_provas_listagem_endpoints) — a fonte da
 * verdade é a RLS, não a UI.
 */
test.describe("proteção da listagem de provas", () => {
  for (const rota of ["/provas", "/provas/abc-123"]) {
    test(`${rota} sem sessão redireciona para /login`, async ({ page }) => {
      await page.goto(rota);
      await expect(page).toHaveURL(/\/login/);
    });
  }
});

test.describe("Provas digitais (E2E_LIVE)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!process.env.E2E_LIVE, "requer E2E_LIVE=1 + sessão + API + provas semeadas");
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await page.setViewportSize(DESKTOP);
    await page.goto("/provas");
    await expect(page.getByRole("heading", { name: "Provas digitais" })).toBeVisible();
  });

  test("tabela fiel ao design e barra de filtros", async ({ page }) => {
    for (const col of [
      "Requerimento",
      "Nome",
      "Cliente",
      "Vendedor",
      "Status",
      "Rota",
      "Criada em",
    ]) {
      await expect(page.getByRole("columnheader", { name: col })).toBeVisible();
    }
    await expect(page.getByLabel("Buscar por nome ou requerimento")).toBeVisible();
    await expect(page.getByRole("button", { name: "Limpar" })).toBeVisible();
  });

  test("filtro de status sincroniza na URL (refresh-safe — DP-5)", async ({ page }) => {
    await page.getByRole("button", { name: "Filtrar por status" }).click();
    await page.getByRole("option", { name: "Cancelada" }).click();
    await expect(page).toHaveURL(/status=cancelada/);
    // sobrevive ao refresh
    await page.reload();
    await expect(page).toHaveURL(/status=cancelada/);
  });

  test("'Ver' navega para o detalhe /provas/{id} (placeholder C08 — DP-6)", async ({ page }) => {
    await page.getByRole("button", { name: "Ver" }).first().click();
    await expect(page).toHaveURL(/\/provas\/[^/]+$/);
  });
});
