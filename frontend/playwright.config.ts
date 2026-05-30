import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e config (F.12b).
 *
 * Drives the real frontend at http://localhost:3000 against the real
 * FastAPI backend on http://localhost:8000. Tests assume:
 *
 *  * the seed admin (scripts/seed_demo_account.py) exists:
 *    demo@example.com / Password123!
 *  * Postgres + Redis are up (docker compose).
 *
 * Resources created by tests carry a millisecond suffix so re-running
 * the suite doesn't collide with leftover state.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  // Sequential by default — every test hits the same demo account, so
  // running in parallel would race on the backend state.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Pick up the dev server if it's already running (the common case
  // when iterating); otherwise spawn one for the run.
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
