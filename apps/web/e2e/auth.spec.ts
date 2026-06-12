import { expect, test } from "@playwright/test";

const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1440, height: 900 };

test.describe("Login e sessão (W1-C03)", () => {
  test("desktop: /login mostra o split com o formulário", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Fazer login" })).toBeVisible();
    await expect(page.getByLabel("E-mail:")).toBeVisible();
    await expect(page.getByLabel("Senha:")).toBeVisible();
    await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
    await expect(page.getByText("©3Studio 2026")).toBeVisible();
    // Espera a entrada coreografada (fade/slide) assentar antes do print.
    await expect(page.getByRole("heading", { name: "Fazer login" })).toHaveCSS("opacity", "1");
    await page.screenshot({ path: "e2e/__screenshots__/login-desktop.png", fullPage: true });
  });

  test("mobile: boas-vindas aparecem primeiro; Entrar revela o login (mesmo /login)", async ({
    page,
  }) => {
    await page.setViewportSize(MOBILE);
    await page.goto("/login");

    // Boas-vindas PRIMEIRO no mobile (overlay sobre o formulário).
    const welcome = page.getByRole("region", { name: "Boas-vindas" });
    await expect(welcome).toBeVisible();
    const welcomeTitle = welcome.getByRole("heading", { name: "Seja bem vindo!" });
    await expect(welcomeTitle).toBeVisible();
    await expect(welcomeTitle).toHaveCSS("opacity", "1"); // espera a entrada assentar
    await page.screenshot({ path: "e2e/__screenshots__/bem-vindo-mobile.png", fullPage: true });

    // Só ao clicar em "Entrar" o formulário é revelado (sem trocar de URL).
    await welcome.getByRole("button", { name: "Entrar" }).click();
    await expect(welcome).toBeHidden();
    await expect(page.getByRole("heading", { name: "Fazer login" })).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
    await page.screenshot({ path: "e2e/__screenshots__/login-mobile.png", fullPage: true });
  });

  test("mobile: touch targets ≥ 44px (RNF-013)", async ({ page }) => {
    await page.setViewportSize(MOBILE);
    await page.goto("/login");
    // Revela o formulário (sai das boas-vindas) antes de medir os controles.
    await page
      .getByRole("region", { name: "Boas-vindas" })
      .getByRole("button", { name: "Entrar" })
      .click();
    await expect(page.getByRole("heading", { name: "Fazer login" })).toBeVisible();
    for (const sel of ['input[name="email"]', 'input[name="senha"]', 'button[type="submit"]']) {
      const box = await page.locator(sel).boundingBox();
      expect(box, sel).not.toBeNull();
      expect(box?.height ?? 0, sel).toBeGreaterThanOrEqual(44);
    }
  });

  test("foco do input faz o contorno aparecer (fade) e some ao desfocar", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await page.goto("/login");
    const emailRing = page.locator('input[name="email"] + span');
    await expect(emailRing).toHaveCSS("opacity", "0");
    await page.getByLabel("E-mail:").focus();
    await expect(emailRing).toHaveCSS("opacity", "1");
    await page.getByLabel("Senha:").focus(); // desfoca o e-mail
    await expect(emailRing).toHaveCSS("opacity", "0");
  });

  test("credenciais inválidas → mensagem genérica (sem revelar o campo)", async ({ page }) => {
    // Mocka só o endpoint de token do Supabase: signInWithPassword falha (400).
    await page.route("**/auth/v1/token**", (route) =>
      route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({
          error: "invalid_grant",
          error_description: "Invalid login credentials",
        }),
      }),
    );
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill("naoexiste@3studio.test");
    await page.getByLabel("Senha:").fill("senhaerrada");
    await page.getByRole("button", { name: "Entrar" }).click();

    // <p role="alert"> do formulário (evita o route-announcer global do Next).
    const alert = page.locator('p[role="alert"]');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(/e-mail ou senha inv[aá]lidos/i);
    await expect(alert).not.toContainText(/credentials/i);
    await expect(page).toHaveURL(/\/login/);
  });
});

// Caminho feliz AUTENTICADO ponta-a-ponta: requer sessão REAL (a checagem
// getUser do servidor não é interceptável por route mock), API rodando e um
// usuário semeado. Por isso fica atrás de E2E_LIVE=1 (passo em docs/auth.md).
// A lógica de sucesso (redirect → app shell) já é coberta pelo teste de
// componente de LoginPanel.
test("caminho feliz: login válido entra no app shell (W1-C04)", async ({ page }) => {
  test.skip(!process.env.E2E_LIVE, "requer E2E_LIVE=1 + usuário semeado + API rodando");
  const email = process.env.E2E_EMAIL ?? "";
  const senha = process.env.E2E_PASSWORD ?? "";
  await page.goto("/login");
  await page.getByLabel("E-mail:").fill(email);
  await page.getByLabel("Senha:").fill(senha);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/usuarios$/);
  // Shell de pé: sidebar com navegação + página de usuários dentro dele.
  await expect(page.getByRole("navigation", { name: "Navegação principal" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Gerenciador de usuários" })).toBeVisible();
});
