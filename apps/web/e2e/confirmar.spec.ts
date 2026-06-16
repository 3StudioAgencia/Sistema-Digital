import { expect, test } from "@playwright/test";

const MOBILE = { width: 390, height: 844 };

/**
 * Confirmação da movimentação (W3-C12) — fecha o laço identificar → assinar →
 * confirmar, mobile-first.
 *
 * Sem credenciais: `/provas/<id>/confirmar` exige autenticação (redirect →
 * /login). Com E2E_LIVE=1 + E2E_CODIGO (código de uma prova que o usuário de teste
 * é o próximo ator a movimentar): após identificar pelo Manual, a tela de
 * confirmação apresenta AUTOMATICAMENTE a assinatura (RF-028) — o pad + o botão de
 * confirmação. O E2E NÃO submete (não muta dado de produção): a transição
 * atômica/idempotente + o vínculo assinatura↔movimentação são cobertos no backend
 * (test_transicoes_endpoints) e a orquestração nos testes de componente.
 */
test.describe("proteção da tela de confirmação", () => {
  test("/provas/<id>/confirmar sem sessão redireciona para /login", async ({ page }) => {
    await page.goto("/provas/00000000-0000-0000-0000-000000000000/confirmar");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Confirmar movimentação (E2E_LIVE)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(
      !process.env.E2E_LIVE || !process.env.E2E_CODIGO,
      "requer E2E_LIVE=1 + E2E_CODIGO (prova em que o usuário é o próximo ator) + sessão + API",
    );
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await page.setViewportSize(MOBILE);
  });

  test("identificar → a assinatura é apresentada automaticamente (RF-028)", async ({ page }) => {
    await page.goto("/escanear");
    await page.getByRole("radio", { name: /Manual/ }).click();
    await page.getByLabel(/Código da prova/).fill(process.env.E2E_CODIGO ?? "");
    await page.getByRole("button", { name: /Buscar prova/ }).click();

    // Navegou para a confirmação e a assinatura aparece automaticamente.
    await expect(page).toHaveURL(/\/provas\/.+\/confirmar$/);
    await expect(page.getByRole("heading", { name: "Assinatura Digital" })).toBeVisible();
    await expect(page.getByLabel(/Área de assinatura/)).toBeVisible();
    // Um dos caminhos do fluxo (assinar OU aprovar) está disponível ao próximo ator.
    const confirmar = page.getByRole("button", { name: "Confirmar" });
    const aprovar = page.getByRole("button", { name: "Aprovar" });
    await expect(confirmar.or(aprovar)).toBeVisible();
  });
});
