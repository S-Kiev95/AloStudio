import { expect, test } from "@playwright/test";

import { accountIdFromUrl, login, unique } from "./helpers";

test.describe("Help Center", () => {
  test("admin creates a portal, then it renders on the public site", async ({
    page,
  }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());

    const name = unique("E2E Portal");
    const slug = unique("e2e-portal");

    // Create via the admin form.
    await page.goto(`/accounts/${accountId}/help-center`);
    await expect(
      page.getByRole("heading", { name: /help center/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /nuevo portal/i }).click();
    await page.getByLabel(/nombre/i).first().fill(name);
    await page.getByLabel(/slug/i).fill(slug);
    await page.getByRole("button", { name: /crear portal/i }).click();

    // Lands back on the list with the new row visible.
    await expect(page.getByText(name)).toBeVisible();

    // Visit the public site for that portal.
    await page.goto(`/hc/${slug}`);
    // Portal name in the public header.
    await expect(
      page.getByRole("link", { name: new RegExp(name) }),
    ).toBeVisible();
    // Empty state for articles.
    await expect(
      page.getByText(/todavía no hay artículos publicados/i),
    ).toBeVisible();
  });
});
