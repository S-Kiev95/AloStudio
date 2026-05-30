import { type Page, expect } from "@playwright/test";

export const DEMO_EMAIL = "demo@example.com";
export const DEMO_PASSWORD = "Password123!";

/**
 * Log in via the real UI form. Lands on the account dashboard
 * (the cookie/devise-header bridge fires server-side in the BFF route).
 */
export async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(DEMO_EMAIL);
  await page.getByLabel(/contraseña/i).fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: /entrar/i }).click();
  // router.push() is a soft navigation — no "load" event fires, so use
  // toHaveURL which polls until it matches instead of waitForURL's
  // "wait until 'load'" default.
  await expect(page).toHaveURL(/\/accounts\/\d+/, { timeout: 15_000 });
  // The account name shows up in the topbar once the shell mounts —
  // a faster + more reliable signal than the "Inicio" page heading
  // (which is hidden behind loading.tsx during the initial stream).
  await expect(page.getByText(/Demo Co/).first()).toBeVisible({
    timeout: 15_000,
  });
}

/** A millisecond-suffixed name so reruns don't collide on the backend. */
export function unique(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}`;
}

/** Pull the active accountId out of the current URL ("/accounts/N/..."). */
export function accountIdFromUrl(url: string): string {
  const m = url.match(/\/accounts\/(\d+)/);
  if (!m) throw new Error(`no accountId in URL: ${url}`);
  return m[1];
}
