import { expect, test } from "@playwright/test";

import { accountIdFromUrl, login, unique } from "./helpers";

/**
 * v2.1 / v2.2 closeout — exercise the Contacts surface end-to-end.
 *
 * Single happy-path test: create a contact, see it in the list, search
 * for it by name, open the detail view, then clean up. Splitting into
 * smaller tests would re-seed + re-login per case and the suite runs
 * serially anyway, so one scenario keeps the runtime bounded.
 */
test.describe("contacts", () => {
  test("create, search, open detail, then delete", async ({ page }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());

    // ----- list page renders ------------------------------------------------
    await page.goto(`/accounts/${accountId}/contacts`);
    await expect(
      page.getByRole("heading", { name: /contactos/i }),
    ).toBeVisible();

    // ----- create -----------------------------------------------------------
    const fullName = unique("E2E Contact");
    const email = `${unique("e2e")}@contact.example.com`;
    await page.getByRole("link", { name: /nuevo contacto/i }).click();
    await expect(page).toHaveURL(/\/contacts\/new$/);

    await page.getByLabel("Nombre").fill(fullName);
    await page.getByLabel("Email").fill(email);
    await page.getByRole("button", { name: /crear contacto/i }).click();

    // The detail view lands at /contacts/:id — the heading is the name.
    await expect(page).toHaveURL(/\/contacts\/\d+$/, { timeout: 10_000 });
    await expect(
      page.getByRole("heading", { name: fullName }),
    ).toBeVisible();
    await expect(page.getByText(email)).toBeVisible();

    // ----- search from the list --------------------------------------------
    await page.goto(`/accounts/${accountId}/contacts`);
    await page.getByLabel(/buscar contactos/i).fill(fullName);
    // The search query is debounced + paginated; wait for the row to
    // surface rather than racing the input keystrokes.
    await expect(page.getByText(fullName, { exact: true })).toBeVisible({
      timeout: 10_000,
    });

    // ----- open the detail from the search result --------------------------
    await page.getByText(fullName, { exact: true }).click();
    await expect(page).toHaveURL(/\/contacts\/\d+$/);
    await expect(
      page.getByRole("heading", { name: fullName }),
    ).toBeVisible();

    // ----- delete (cleanup so the demo account doesn't accrete ghosts) -----
    // Delete lives on the LIST row, not the detail view. Go back to the
    // list, search to narrow to our contact, then delete its row.
    await page.goto(`/accounts/${accountId}/contacts`);
    await page.getByLabel(/buscar contactos/i).fill(fullName);
    const row = page.locator("li", { hasText: fullName });
    await expect(row).toBeVisible({ timeout: 10_000 });

    // Each row has an aria-label="Eliminar" button guarded by a
    // window.confirm() — auto-accept it (same pattern as labels.spec.ts).
    page.once("dialog", (d) => d.accept());
    await row.getByRole("button", { name: /eliminar/i }).click();

    // …and the row disappears from the (still-filtered) list.
    await expect(
      page.getByText(fullName, { exact: true }),
    ).toBeHidden({ timeout: 10_000 });
  });
});
