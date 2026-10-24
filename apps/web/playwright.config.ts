import { defineConfig } from "@playwright/test";

const port = Number(process.env.E2E_PORT ?? 3032);
const baseURL = `http://127.0.0.1:${port}`;

/**
 * Browser journeys run against a production build served with the deployed proxy shape
 * (NEXT_PUBLIC_API_URL=/, same-origin cookies). API calls are answered by the TEST-ONLY
 * contract double in e2e/support — these runs prove UI behaviour, not live integration.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  timeout: 45_000,
  expect: { timeout: 7_500 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 4,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL,
    // The system Chrome channel avoids a separate browser download; CI runners ship Chrome.
    channel: process.env.PLAYWRIGHT_CHANNEL ?? "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "phone-390", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 } },
    { name: "phone-320", use: { viewport: { width: 320, height: 740 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 } },
  ],
  webServer: {
    command: `pnpm exec next build && pnpm exec next start --hostname 127.0.0.1 --port ${port}`,
    url: baseURL,
    env: { NEXT_PUBLIC_API_URL: "/" },
    reuseExistingServer: !process.env.CI && process.env.E2E_REUSE_SERVER === "1",
    timeout: 300_000,
  },
});
