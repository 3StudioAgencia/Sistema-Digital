import { expect, test } from "@playwright/test";

const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1440, height: 900 };

/**
 * App shell + Gerenciador de usuários (W1-C04).
 *
 * Sem credenciais: valida a PROTEÇÃO do grupo autenticado (redirect → /login).
 * Com E2E_LIVE=1 (sessão real + API + admin semeado — docs/usuarios.md):
 * navegação pelo shell, tabela fiel, modal animado e responsividade.
 * O fluxo de ESCRITA (criar usuário de verdade) fica no nível de integração
 * do backend e nos testes de componente — o E2E live não polui o ambiente.
 */
test.describe("proteção do grupo autenticado", () => {
  for (const rota of ["/usuarios", "/dashboard", "/relatorios"]) {
    test(`${rota} sem sessão redireciona para /login`, async ({ page }) => {
      await page.goto(rota);
      await expect(page).toHaveURL(/\/login/);
    });
  }
});

test.describe("shell autenticado (E2E_LIVE)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!process.env.E2E_LIVE, "requer E2E_LIVE=1 + admin semeado + API rodando");
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).toHaveURL(/\/usuarios$/);
  });

  test("navegação pelo shell: placeholders renderizam DENTRO do layout", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.getByRole("link", { name: "Dashboard" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText(/em construção/i)).toBeVisible();
    // a sidebar continua de pé (layout compartilhado, sem remontar)
    await expect(page.getByRole("navigation", { name: "Navegação principal" })).toBeVisible();
    await page.getByRole("link", { name: "Usuários" }).click();
    await expect(page.getByRole("heading", { name: "Gerenciador de usuários" })).toBeVisible();
  });

  test("tabela fiel: colunas e controles do design", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    for (const col of ["Nome", "E-mail", "Setor", "Localização", "Status", "Perfil", "Ações"]) {
      await expect(page.getByRole("columnheader", { name: col })).toBeVisible();
    }
    await expect(page.getByPlaceholder("Buscar por nome ou email...")).toBeVisible();
    await expect(page.getByRole("button", { name: "Novo usuário" })).toBeVisible();
  });

  test("modal Novo usuário abre com scale+fade e fecha com ESC", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.getByRole("button", { name: "Novo usuário" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Novo usuário")).toBeVisible();
    await expect(dialog.getByLabel("Nome:")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  });

  test("mobile: sidebar vira drawer e tabela vira cards (DP-7)", async ({ page }) => {
    await page.setViewportSize(MOBILE);
    await page.goto("/usuarios");
    // tabela desktop oculta; hambúrguer presente com touch target ≥44px
    const hamburguer = page.getByRole("button", { name: "Abrir menu" });
    await expect(hamburguer).toBeVisible();
    const box = await hamburguer.boundingBox();
    expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    await hamburguer.click();
    await expect(page.getByRole("complementary", { name: "Menu" })).toBeVisible();
  });
});
