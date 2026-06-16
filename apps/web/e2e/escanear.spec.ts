import { expect, test } from "@playwright/test";

const MOBILE = { width: 390, height: 844 };

/**
 * Escanear prova (W3-C10) — a ponte física→digital, mobile-first.
 *
 * Sem credenciais: `/escanear` é universal (Matriz §7) mas exige autenticação
 * (redirect → /login). Com E2E_LIVE=1 (sessão real + API): a tela mostra os dois
 * modos (Câmera/Manual); no Manual, um código bem-formado porém inexistente
 * devolve a MESMA mensagem genérica (anti-enumeração — RN-014), sem revelar nada.
 *
 * A leitura por câmera (getUserMedia), o escopo por perfil (RLS) e o rate
 * limiting são cobertos no backend (test_provas_identificacao_*) e nos testes de
 * componente (escanear-view) — a fonte da verdade não é o E2E.
 */
test.describe("proteção da tela de escaneamento", () => {
  test("/escanear sem sessão redireciona para /login", async ({ page }) => {
    await page.goto("/escanear");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Escanear prova (E2E_LIVE)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!process.env.E2E_LIVE, "requer E2E_LIVE=1 + sessão + API");
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).not.toHaveURL(/\/login/);
    await page.setViewportSize(MOBILE); // o C10 é primariamente mobile (RF-029)
    await page.goto("/escanear");
  });

  test("mostra os dois modos e o campo manual (formato do C06)", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Escanear prova" })).toBeVisible();
    await expect(page.getByRole("radio", { name: /Câmera/ })).toBeVisible();
    await expect(page.getByRole("radio", { name: /Manual/ })).toBeVisible();

    await page.getByRole("radio", { name: /Manual/ }).click();
    await expect(page.getByLabel(/Código da prova/)).toBeVisible();
    await expect(page.getByRole("button", { name: /Buscar prova/ })).toBeDisabled();
  });

  test("código bem-formado e inexistente → mensagem genérica (anti-enumeração)", async ({
    page,
  }) => {
    await page.getByRole("radio", { name: /Manual/ }).click();
    // Formato válido (PRV-AAAA-MM-NNNNNN) mas que não existe — habilita o botão e
    // resolve no MESMO 404 genérico de "fora do escopo".
    await page.getByLabel(/Código da prova/).fill("PRV-2000-01-ZZZZZZ");
    await page.getByRole("button", { name: /Buscar prova/ }).click();
    await expect(page.getByText("Prova não encontrada.")).toBeVisible();
    await expect(page).toHaveURL(/\/escanear$/); // não navegou (nada a confirmar)
  });
});
