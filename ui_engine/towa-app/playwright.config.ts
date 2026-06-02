import { defineConfig, devices } from '@playwright/test'

// Cloud-mode end-to-end suite for #39.
// Required external services (NOT auto-started by this config):
//   - PostgreSQL (db)        — via `docker compose up db -d` at the monorepo root
//   - service_engine API     — via `docker compose up service-engine -d`
//
// Run `npm run e2e` after the above are healthy.

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: process.env.E2E_NO_DEV_SERVER
    ? undefined
    : {
        command: 'npm run dev -- --port 5173',
        url: 'http://localhost:5173',
        reuseExistingServer: true,
        timeout: 60_000,
      },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
