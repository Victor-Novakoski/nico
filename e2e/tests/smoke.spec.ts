import { expect, test } from "@playwright/test";

const username = process.env.E2E_USERNAME ?? "e2e";
const password = process.env.E2E_PASSWORD ?? "";

test("a tela de login abre", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Nico" })).toBeVisible();
  await expect(page.getByLabel("Usuário")).toBeVisible();
  await expect(page.getByLabel("Senha")).toBeVisible();
  await expect(page.getByRole("button", { name: "Entrar" })).toBeVisible();
});

test("o login leva à tela inicial", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Usuário").fill(username);
  await page.getByLabel("Senha").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(
    page.getByRole("heading", { name: "Lançar gastos" }),
  ).toBeVisible();
});
