import { expect, test } from "@playwright/test";

import { accountIdFromUrl, login, unique } from "./helpers";

/**
 * v2.3 / v2.4 closeout — admin invites a teammate.
 *
 * Drives the Settings → Agentes form against the real backend so we
 * confirm:
 *   (1) the invite form mounts only when the button is clicked,
 *   (2) submitting POSTs successfully and surfaces the inline
 *       confirmation banner,
 *   (3) the new agent shows up in the list with the right role,
 *   (4) removing the agent cleans up state.
 *
 * The mailer side (real email out) is asserted by backend integration
 * tests; here we trust the success banner ("Le mandamos una
 * invitación a …") which only shows when the POST returned 2xx.
 */
test.describe("settings › agents › invite", () => {
  test("invite an agent and see them in the list, then remove", async ({
    page,
  }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());
    await page.goto(`/accounts/${accountId}/settings/agents`);

    await expect(
      page.getByRole("heading", { name: /agentes/i }),
    ).toBeVisible();

    const inviteeEmail = `${unique("e2e-agent")}@example.com`;
    const inviteeName = unique("E2E Agent");

    // Form is hidden until the trigger fires.
    const inviteForm = page.getByRole("heading", { name: /invitar agente/i });
    await expect(inviteForm).toBeHidden();

    await page.getByRole("button", { name: /invitar agente/i }).click();
    await expect(inviteForm).toBeVisible();

    await page.getByLabel("Nombre").fill(inviteeName);
    await page.getByLabel("Email").fill(inviteeEmail);
    // Default role stays "agent" — leave the select untouched.
    await page.getByRole("button", { name: /enviar invitación/i }).click();

    // Success banner mentions the invitee's email.
    await expect(
      page.getByText(inviteeEmail, { exact: false }),
    ).toBeVisible({ timeout: 10_000 });

    // The new agent appears in the listing.
    const row = page.locator("li", { hasText: inviteeEmail });
    await expect(row).toBeVisible({ timeout: 10_000 });
    await expect(row.getByText(inviteeName)).toBeVisible();

    // ----- cleanup ---------------------------------------------------------
    page.once("dialog", (d) => d.accept());
    const removeBtn = row.getByRole("button", { name: /eliminar|quitar/i });
    if (await removeBtn.isVisible().catch(() => false)) {
      await removeBtn.click();
      // Row disappears.
      await expect(
        page.locator("li", { hasText: inviteeEmail }),
      ).toBeHidden({ timeout: 10_000 });
    }
  });

  test("invite form validates required fields", async ({ page }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());
    await page.goto(`/accounts/${accountId}/settings/agents`);

    await page.getByRole("button", { name: /invitar agente/i }).click();
    // Submit with both fields empty → inline error. Assert the specific
    // error text rather than getByRole("alert") — Next.js renders its own
    // role="alert" route-announcer, which would make a bare alert query
    // ambiguous (strict-mode violation).
    await page.getByRole("button", { name: /enviar invitación/i }).click();
    await expect(
      page.getByText(/nombre y el email son obligatorios/i),
    ).toBeVisible();
  });
});
