import { defineConfig, devices } from '@playwright/test';

/**
 * Browser-driven visual acceptance (#112, #154).
 *
 * Deliberately not part of the default `npm test`: it needs a running backend
 * with seeded fixtures and a downloaded browser, so it is an explicit,
 * reproducible gate rather than something that silently blocks unit runs.
 * See docs/PROTOTYPE_READINESS_2026-08-02.md for the exact commands.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'e2e-report' }]],
  use: {
    baseURL: process.env.PARTHA_E2E_BASE_URL ?? 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    viewport: { width: 1440, height: 900 },
  },
  // Desktop Chrome's default 1280x720 is overridden so the captured evidence
  // reflects a realistic desktop review viewport.
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
  ],
});
