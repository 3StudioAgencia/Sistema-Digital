import { expect, test } from "@playwright/test";

const DESKTOP = { width: 1440, height: 900 };

/**
 * Configurações do sistema (W2-C09) — exclusiva do 3Studio (Matriz §7).
 *
 * Sem credenciais: a rota exige autenticação (redirect → /login). Com E2E_LIVE=1
 * (sessão real + API): um admin 3Studio abre a tela, salva o tempo de atraso e o
 * valor persiste; um perfil não-3Studio é barrado pelo proxio (redirect) — a
 * negação em profundidade (RLS + 403) é coberta no backend
 * (test_settings_endpoints / test_rls_system_settings), a fonte da verdade.
 */
test.describe("proteção de Configurações", () => {
  test("/configuracoes sem sessão redireciona para /login", async ({ page }) => {
    await page.goto("/configuracoes");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Configurações (E2E_LIVE — admin)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!process.env.E2E_LIVE, "requer E2E_LIVE=1 + sessão admin 3Studio + API");
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await page.setViewportSize(DESKTOP);
    await page.goto("/configuracoes");
  });

  test("salva o tempo de atraso e o valor persiste após recarregar (US-016)", async ({ page }) => {
    const card = page.getByRole("region", { name: "Tempo de atraso" });
    const input = card.getByLabel("Tempo (horas úteis)");
    await input.fill("72");
    await card.getByRole("button", { name: "Salvar" }).click();
    await expect(page.getByText("Configurações salvas.")).toBeVisible();

    await page.reload();
    await expect(
      page.getByRole("region", { name: "Tempo de atraso" }).getByLabel("Tempo (horas úteis)"),
    ).toHaveValue("72");
  });

  test("template personalizado revela os campos do C06 (RN-011/DP-5)", async ({ page }) => {
    const card = page.getByRole("region", { name: "Template de etiqueta" });
    await card.getByRole("radio", { name: "Personalizado" }).click();
    await expect(card.getByLabel("Largura (mm)")).toBeVisible();
    await expect(card.getByLabel("Altura (mm)")).toBeVisible();
  });
});

test.describe("Configurações (E2E_LIVE — não-3Studio)", () => {
  test("perfil não-3Studio não acessa /configuracoes", async ({ page }) => {
    test.skip(!process.env.E2E_LIVE_VENDEDOR, "requer sessão de um perfil não-admin");
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_VENDEDOR_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_VENDEDOR_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await page.goto("/configuracoes");
    // o proxy (C05) redireciona não-admin para fora da rota exclusiva 3Studio
    await expect(page).not.toHaveURL(/\/configuracoes/);
  });
});
