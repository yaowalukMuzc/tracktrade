import { defineConfig, devices } from '@playwright/test'

// E2E_BASE_URL=http://localhost:8080 runs against `docker compose up` (full stack).
// Without it, Playwright starts the Vite dev server; screens that need the API then see a signed-out session.
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5178'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  reporter: [['list']],
  use: { baseURL, locale: 'th-TH', timezoneId: 'Asia/Bangkok' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'], viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : { command: 'npm run dev', url: baseURL, reuseExistingServer: true, timeout: 60_000 },
})
