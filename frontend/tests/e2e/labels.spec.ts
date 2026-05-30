import { expect, test } from "@playwright/test";

import { accountIdFromUrl, login, unique } from "./helpers";

test.describe("settings › labels CRUD", () => {
  test("create a label and see it in the list, then delete it", async ({
    page,
  }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());
    await page.goto(`/accounts/${accountId}/settings/labels`);

    await expect(
      page.getByRole("heading", { name: /etiquetas/i }),
    ).toBeVisible();

    const title = unique("e2e-label");

    // Open the create form
    await page.getByRole("button", { name: /nueva etiqueta/i }).click();
    await page.getByLabel(/título/i).fill(title);

    // Submit
    await page.getByRole("button", { name: /crear etiqueta/i }).click();

    // The new label appears in the listing
    await expect(page.getByText(title, { exact: true })).toBeVisible();

    // Auto-confirm the delete dialog
    page.once("dialog", (dialog) => dialog.accept());

    // Each row has an "Eliminar" icon button. Scope the click to the row.
    const row = page.locator("li", { hasText: title });
    await row.getByRole("button", { name: /eliminar/i }).click();

    // …and disappears.
    await expect(page.getByText(title, { exact: true })).toBeHidden();
  });
});
