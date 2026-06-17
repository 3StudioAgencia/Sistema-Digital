import { expect, test, type Page } from "@playwright/test";

const DESKTOP = { width: 1440, height: 900 };

/**
 * Cancelamento de prova (W3-C14).
 *
 * A cobertura exaustiva é unit/integração (modal, gating por perfil, motor do C11,
 * 403/422/404, idempotência). Aqui ficam os smokes E2E, gated por `E2E_LIVE`
 * (sessão real + API + provas semeadas). O CONFIRMAR é DESTRUTIVO e IRREVERSÍVEL
 * (RN-005) — fica atrás de `E2E_CANCELAR=1` para não cancelar uma prova real num
 * E2E_LIVE de rotina. A negação ao Vendedor exige credenciais próprias.
 */
async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("E-mail:").fill(email);
  await page.getByLabel("Senha:").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.setViewportSize(DESKTOP);
}

async function abrirPrimeiraProva(page: Page): Promise<void> {
  await page.goto("/provas");
  await page.getByRole("button", { name: "Ver" }).first().click();
  await expect(page).toHaveURL(/\/provas\/[^/]+$/);
}

test.describe("Cancelamento — 3Studio (E2E_LIVE)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(
      !process.env.E2E_LIVE,
      "requer E2E_LIVE=1 + sessão 3Studio (admin) + API + provas ATIVAS semeadas",
    );
    await login(page, process.env.E2E_EMAIL ?? "", process.env.E2E_PASSWORD ?? "");
    await abrirPrimeiraProva(page);
  });

  test("o modal exige motivo: confirmar fica bloqueado até preencher (RN-005)", async ({
    page,
  }) => {
    await page.getByRole("button", { name: "Cancelar prova" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("irreversível");
    const confirmar = dialog.getByRole("button", { name: "Cancelar prova" });
    await expect(confirmar).toBeDisabled(); // sem motivo → bloqueado
    await dialog.getByLabel(/Motivo/i).fill("verificação E2E");
    await expect(confirmar).toBeEnabled();
  });

  test("cancela uma prova ativa (com motivo) → Cancelada", async ({ page }) => {
    test.skip(
      !process.env.E2E_CANCELAR,
      "ação DESTRUTIVA e IRREVERSÍVEL — requer E2E_CANCELAR=1 + prova descartável",
    );
    await page.getByRole("button", { name: "Cancelar prova" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel(/Motivo/i).fill("cancelamento de teste E2E");
    await dialog.getByRole("button", { name: "Cancelar prova" }).click();
    await expect(page.getByText("Prova cancelada.")).toBeVisible();
    // A ação some (estado terminal — irreversível).
    await expect(page.getByRole("button", { name: "Cancelar prova" })).toHaveCount(0);
  });
});

test.describe("Cancelamento — acesso do Vendedor (E2E_LIVE)", () => {
  test("como Vendedor, a ação de cancelar NÃO está disponível", async ({ page }) => {
    test.skip(
      !process.env.E2E_LIVE || !process.env.E2E_VENDEDOR_EMAIL,
      "requer E2E_LIVE=1 + credenciais de Vendedor (E2E_VENDEDOR_EMAIL/PASSWORD)",
    );
    await login(
      page,
      process.env.E2E_VENDEDOR_EMAIL ?? "",
      process.env.E2E_VENDEDOR_PASSWORD ?? "",
    );
    await abrirPrimeiraProva(page);
    await expect(page.getByRole("button", { name: "Cancelar prova" })).toHaveCount(0);
  });
});
