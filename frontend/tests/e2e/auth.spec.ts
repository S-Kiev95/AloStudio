import { expect, test } from "@playwright/test";

import { DEMO_EMAIL, DEMO_PASSWORD, login } from "./helpers";

test.describe("auth", () => {
  test("unauthenticated visit to /accounts redirects to /login", async ({ page }) => {
    await page.goto("/accounts");
    await expect(page).toHaveURL(/\/login/);
  });

  test("login lands on the account dashboard", async ({ page }) => {
    await login(page);
    // Account-switcher renders the name in both the chip + dropdown link,
    // pick the first occurrence (the chip in the topbar).
    await expect(page.getByText(/Demo Co/).first()).toBeVisible();
  });

  test("wrong password shows an inline error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(DEMO_EMAIL);
    await page.getByLabel(/contraseña/i).fill(`${DEMO_PASSWORD}-wrong`);
    await page.getByRole("button", { name: /entrar/i }).click();
    // Devise returns 401; the form surfaces the error inline.
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("alert")).toBeVisible();
  });
});
