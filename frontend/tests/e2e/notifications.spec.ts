import { expect, test } from "@playwright/test";

import { accountIdFromUrl, login } from "./helpers";

/**
 * v2.5 / v2.6 closeout — exercise the notifications surface.
 *
 * The demo account may or may not have notifications already (depends
 * on prior runs). To make the spec deterministic, we don't assert a
 * specific badge count — instead we assert the elements exist + the
 * Settings → Notificaciones page lets us toggle preferences without
 * a server error.
 *
 * The live "bell increments on assignment" path needs two logged-in
 * users which Playwright's single-context can't simulate cleanly here.
 * Backend integration test already covers the listener's row insert
 * + cable broadcast (tests/integration/test_notifications.py — 8/8
 * green), so this spec focuses on the frontend's wire shape.
 */
test.describe("notifications", () => {
  test("topbar bell opens a dropdown with the inbox", async ({ page }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());

    // The bell is a <summary> with an aria-label starting "Notificaciones"
    // (a native disclosure widget — not a button role, so target the
    // element + its label directly).
    const bell = page.locator('summary[aria-label^="Notificaciones"]');
    await expect(bell).toBeVisible();
    await bell.click();

    // The dropdown is a <dialog role="dialog" aria-label="Notificaciones">.
    const dropdown = page.getByRole("dialog", { name: /notificaciones/i });
    await expect(dropdown).toBeVisible();

    // It either lists notifications or shows the empty state; both
    // are correct. Just confirm the header rendered.
    await expect(
      dropdown.getByRole("heading", { name: /notificaciones/i }),
    ).toBeVisible();

    // "Marcar todo" button is always present in the dropdown header.
    await expect(
      dropdown.getByRole("button", { name: /marcar todo/i }),
    ).toBeVisible();

    // Close by clicking outside.
    await page.mouse.click(20, 20);
    await expect(dropdown).toBeHidden();
  });

  test("full inbox page renders and the filter toggles work", async ({
    page,
  }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());
    await page.goto(`/accounts/${accountId}/notifications`);

    await expect(
      page.getByRole("heading", { name: /notificaciones/i }).first(),
    ).toBeVisible();

    // Tabs: "Todas" and "No leídas". Both must be present.
    const allTab = page.getByRole("tab", { name: /todas/i });
    const unreadTab = page.getByRole("tab", { name: /no leídas/i });
    await expect(allTab).toBeVisible();
    await expect(unreadTab).toBeVisible();

    // Flip to unread; the active state should change.
    await unreadTab.click();
    await expect(unreadTab).toHaveAttribute("aria-selected", "true");

    // Flip back.
    await allTab.click();
    await expect(allTab).toHaveAttribute("aria-selected", "true");
  });

  test("settings → notificaciones lets the user toggle a preference", async ({
    page,
  }) => {
    await login(page);
    const accountId = accountIdFromUrl(page.url());
    await page.goto(`/accounts/${accountId}/settings/notifications`);

    await expect(
      page.getByRole("heading", { name: /notificaciones/i }),
    ).toBeVisible();

    // First load lazily seeds defaults (every type subscribed). The
    // checkbox for "Email — Conversación asignada" must be present.
    const emailCheckbox = page.getByLabel(/email — conversación asignada/i);
    await expect(emailCheckbox).toBeVisible();

    // Flip it off + save → success banner.
    const wasChecked = await emailCheckbox.isChecked();
    if (wasChecked) {
      await emailCheckbox.uncheck();
    } else {
      await emailCheckbox.check();
    }
    await page.getByRole("button", { name: /guardar cambios/i }).click();
    await expect(page.getByText(/preferencias guardadas/i)).toBeVisible({
      timeout: 10_000,
    });

    // Restore the original state so the spec is idempotent across
    // re-runs against the shared demo account.
    if (wasChecked) {
      await emailCheckbox.check();
    } else {
      await emailCheckbox.uncheck();
    }
    await page.getByRole("button", { name: /guardar cambios/i }).click();
    await expect(page.getByText(/preferencias guardadas/i)).toBeVisible();
  });
});
