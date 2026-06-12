import { expect, test } from "@playwright/test";

const DESKTOP = { width: 1440, height: 900 };

// JPEG mínimo válido pelos magic bytes (o backend valida o CONTEÚDO).
const JPEG_MINIMO = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0, 0, 0, 0, 0]);

/**
 * Criação de Prova Digital (W2-C06).
 *
 * Sem credenciais: valida a PROTEÇÃO da rota (redirect → /login). Com
 * E2E_LIVE=1 (sessão real de ADMIN + API): fidelidade do formulário e
 * validações — sem escrita, na mesma filosofia do shell-usuarios.spec.
 * O caminho feliz de ESCRITA (cria prova de verdade + baixa a etiqueta) é
 * opt-in via E2E_LIVE_ESCRITA=1, para não poluir o ambiente por padrão.
 * O acesso negado por perfil exige credenciais de um usuário NÃO-admin
 * (E2E_EMAIL_NAO_ADMIN / E2E_PASSWORD_NAO_ADMIN).
 */
test.describe("proteção da rota", () => {
  test("/provas/nova sem sessão redireciona para /login", async ({ page }) => {
    await page.goto("/provas/nova");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("nova prova (E2E_LIVE)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!process.env.E2E_LIVE, "requer E2E_LIVE=1 + admin semeado + API rodando");
    await page.setViewportSize(DESKTOP);
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();
    await page.getByRole("link", { name: "Nova prova" }).click();
    await expect(page).toHaveURL(/\/provas\/nova$/);
  });

  test("formulário fiel ao design: campos, rota em 4 opções e dropzone", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Nova prova Digital" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Criar Prova" })).toBeVisible();
    for (const rotulo of ["Nome", "Requerimento", "Cliente"]) {
      await expect(page.getByLabel(rotulo)).toBeVisible();
    }
    await expect(page.getByRole("button", { name: "Vendedor" })).toBeVisible();
    const rotas = page.getByRole("radio");
    await expect(rotas).toHaveText(["Matriz", "Filial", "Lam. Matriz", "Lam. Filial"]);
    await expect(page.getByText("Solte ou clique")).toBeVisible();
    await expect(page.getByText("JPG • PNG")).toBeVisible();
  });

  test("criar sem preencher mostra erros claros (incl. rota — RF-001/RN-007)", async ({ page }) => {
    await page.getByRole("button", { name: "Criar Prova" }).click();
    await expect(page.getByText("Selecione a rota de encaminhamento.")).toBeVisible();
    await expect(page.getByText("Informe o nome da prova.")).toBeVisible();
    await expect(page.getByText("Anexe a arte da prova (JPG ou PNG, até 10 MB).")).toBeVisible();
    await expect(page).toHaveURL(/\/provas\/nova$/); // nada foi criado/navegado
  });

  test("caminho feliz: cria prova e baixa a etiqueta (E2E_LIVE_ESCRITA)", async ({ page }) => {
    test.skip(!process.env.E2E_LIVE_ESCRITA, "escrita real é opt-in (polui o ambiente)");
    await page.getByLabel("Nome").fill("Prova E2E");
    await page.getByLabel("Requerimento").fill("999001");
    await page.getByLabel("Cliente").fill("Cliente E2E");
    await page.getByRole("button", { name: "Vendedor" }).click();
    await page.getByRole("option").first().click();
    await page.getByRole("radio", { name: "Matriz" }).click();
    await page
      .locator('input[type="file"]')
      .setInputFiles({ name: "arte.jpg", mimeType: "image/jpeg", buffer: JPEG_MINIMO });

    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Criar Prova" }).click();
    const arquivo = await download;
    expect(arquivo.suggestedFilename()).toMatch(
      /^etiqueta-PRV-\d{4}-\d{2}-[2-9A-HJ-KM-NP-Z]{6}\.pdf$/,
    );
    await expect(page).toHaveURL(/\/provas$/); // placeholder do C07 (DP-7)
  });
});

test.describe("acesso negado por perfil (E2E_LIVE + não-admin)", () => {
  test("não-admin em /provas/nova: redirect + toast genérico (Matriz §7)", async ({ page }) => {
    test.skip(
      !process.env.E2E_LIVE || !process.env.E2E_EMAIL_NAO_ADMIN,
      "requer E2E_LIVE=1 + credenciais de usuário não-admin",
    );
    await page.goto("/login");
    await page.getByLabel("E-mail:").fill(process.env.E2E_EMAIL_NAO_ADMIN ?? "");
    await page.getByLabel("Senha:").fill(process.env.E2E_PASSWORD_NAO_ADMIN ?? "");
    await page.getByRole("button", { name: "Entrar" }).click();

    await page.goto("/provas/nova");
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText("Você não tem permissão para acessar essa página.")).toBeVisible();
  });
});
