import { expect, test } from "@playwright/test";

const DESKTOP = { width: 1440, height: 900 };

/**
 * Detalhe da prova (W2-C08).
 *
 * Sem credenciais: a rota `/provas/{id}` é universal mas exige autenticação
 * (redirect → /login). Com E2E_LIVE=1 (sessão real + API + provas semeadas):
 * abre o detalhe a partir do "Ver" da listagem, valida o card (arte, metadados,
 * botões de etiqueta), o empty state do histórico (DP-2) e o "Voltar" (DP-6).
 *
 * O ESCOPO por perfil e o ANTI-VAZAMENTO (fora do escopo → mesmo 404) são
 * cobertos à exaustão no backend (test_provas_detalhe_endpoints) — a fonte da
 * verdade é a RLS, não a UI.
 */
test.describe("proteção do detalhe da prova", () => {
  test("/provas/{id} sem sessão redireciona para /login", async ({ page }) => {
    await page.goto("/provas/11111111-1111-1111-1111-111111111111");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Detalhe da prova (E2E_LIVE)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!process.env.E2E_LIVE, "requer E2E_LIVE=1 + sessão + API + provas semeadas");
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await page.setViewportSize(DESKTOP);
    await page.goto("/provas");
    await page.getByRole("button", { name: "Ver" }).first().click();
    await expect(page).toHaveURL(/\/provas\/[^/]+$/);
  });

  test("card com metadados, ações de etiqueta e histórico em empty state", async ({ page }) => {
    await expect(page.getByRole("button", { name: /Voltar/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Visualizar etiqueta" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Baixar etiqueta" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Histórico de movimentações" })).toContainText(
      "Esta prova ainda não teve movimentações.",
    );
  });

  test("'Visualizar etiqueta' abre o preview em modal (DP-4)", async ({ page }) => {
    await page.getByRole("button", { name: "Visualizar etiqueta" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("dialog")).toContainText("Etiqueta —");
  });

  test("'Voltar' retorna à listagem (DP-6)", async ({ page }) => {
    await page.getByRole("button", { name: /Voltar/ }).click();
    await expect(page).toHaveURL(/\/provas$/);
    await expect(page.getByRole("heading", { name: "Provas digitais" })).toBeVisible();
  });
});
