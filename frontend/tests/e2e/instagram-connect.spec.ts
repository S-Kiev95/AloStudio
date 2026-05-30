import { expect, test } from "@playwright/test";

import { accountIdFromUrl, login } from "./helpers";

test.describe("Instagram connection UI", () => {
  test("connection page surfaces both OAuth buttons + manual mode", async ({
    page,
  }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());
    await page.goto(`/accounts/${accountId}/instagram`);

    // Tabs are present.
    await expect(
      page.getByRole("link", { name: /conexión/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /publicaciones/i }),
    ).toBeVisible();

    // The two OAuth buttons render. We don't click them — they'd start a
    // real Meta OAuth roundtrip — only assert they're wired into the UI.
    await expect(
      page.getByRole("button", { name: /facebook login/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /instagram login/i }),
    ).toBeVisible();

    // Manual mode is collapsed by default; expand it.
    await page
      .getByRole("button", { name: /modo avanzado: pegar un token/i })
      .click();

    // The manual form's required fields are visible after expansion.
    await expect(page.getByLabel(/nombre/i)).toBeVisible();
    await expect(page.getByLabel(/access token/i)).toBeVisible();
  });
});
