import { mkdirSync } from "node:fs";
import { join } from "node:path";
import type { Page, TestInfo } from "@playwright/test";
import { ids, PASSWORD } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

/**
 * Opt-in screenshots of every route and state for visual reviews before and after a design
 * change (synthetic data only): E2E_CAPTURE_DIR=/abs/dir pnpm exec playwright test e2e/capture.spec.ts
 */
const dir = process.env.E2E_CAPTURE_DIR ?? "";
test.skip(!dir, "set E2E_CAPTURE_DIR to capture review screenshots");

async function shot(page: Page, name: string, testInfo: TestInfo, fullPage = true) {
  mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: join(dir, `${name}.${testInfo.project.name}.png`), fullPage, animations: "disabled" });
}

async function settled(page: Page) {
  // An open record dialog hides the page heading from the accessibility tree.
  await expect(page.getByRole("dialog").or(page.getByRole("heading", { level: 1 })).first()).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test.describe("household", () => {
  test.use({ scenario: { authRequired: false } });

  for (const [name, path] of [
    ["overview", "/dashboard"],
    ["transactions", "/transactions"],
    ["transactions-selected", `/transactions?selected=${ids.salary}`],
    ["transactions-filtered-empty", "/transactions?q=no-such-merchant"],
    ["review", "/review"],
    ["review-selected", `/review?selected=${ids.duplicate}`],
    ["assistant-idle", "/assistant"],
    ["sources", "/sources"],
    ["privacy", "/privacy"],
    ["demo", "/demo"],
    ["not-found", "/no-such-page"],
  ] as const) {
    test(name, async ({ page }, testInfo) => {
      await page.goto(path);
      await settled(page);
      await shot(page, name, testInfo);
    });
  }

  test("overview-loading", async ({ page, api }, testInfo) => {
    api.delay(/money\/summary/, 20_000);
    await page.goto("/dashboard");
    await expect(page.getByText("Loading your month…")).toBeVisible();
    await shot(page, "overview-loading", testInfo, false);
  });

  test("overview-degraded", async ({ page, api }, testInfo) => {
    api.failNext(/money\/obligations/, 503, "source_unavailable");
    await page.goto("/dashboard");
    await expect(page.getByRole("region", { name: "Bills due" }).getByRole("alert")).toBeVisible();
    await shot(page, "overview-degraded", testInfo);
  });

  test("overview-offline", async ({ page, context }, testInfo) => {
    await page.goto("/dashboard");
    await settled(page);
    await context.setOffline(true);
    await expect(page.getByText("You're offline.")).toBeVisible();
    await shot(page, "overview-offline", testInfo, false);
  });

  test("assistant-pending", async ({ page, api }, testInfo) => {
    api.delay(/assistant\/ask/, 20_000);
    await page.goto("/assistant");
    await page.getByLabel("Your question").fill("How much did I spend this month?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText("Thinking…")).toBeVisible();
    await shot(page, "assistant-pending", testInfo);
  });

  test("assistant-answered", async ({ page }, testInfo) => {
    await page.goto("/assistant");
    await page.getByLabel("Your question").fill("How much did I spend at Sample Books this month?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByRole("article", { name: /Sample Books this month/ }).getByText("October 2026")).toBeVisible();
    await shot(page, "assistant-answered", testInfo);
  });

  for (const [name, id] of [
    ["import-running", ids.runningImport],
    ["import-partial", ids.partialImport],
  ] as const) {
    test(name, async ({ page }, testInfo) => {
      await page.goto(`/import/${id}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForTimeout(600);
      await shot(page, name, testInfo);
    });
  }

  test("landing", async ({ page }, testInfo) => {
    // Reduced motion shows every reveal at once, so the full page captures without scrolling.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?graphics=off");
    await settled(page);
    await shot(page, "landing", testInfo);
    await shot(page, "landing-hero", testInfo, false);
  });
});

test.describe("empty ledger", () => {
  test.use({ scenario: { authRequired: false, emptyLedger: true } });

  for (const [name, path] of [
    ["empty-overview", "/dashboard"],
    ["empty-transactions", "/transactions"],
    ["empty-review", "/review"],
  ] as const) {
    test(name, async ({ page }, testInfo) => {
      await page.goto(path);
      await settled(page);
      await shot(page, name, testInfo);
    });
  }
});

test.describe("signed out", () => {
  test.use({ scenario: { authRequired: true, signedIn: false } });

  test("login", async ({ page }, testInfo) => {
    await page.goto("/login");
    await settled(page);
    await shot(page, "login", testInfo);
    await page.getByLabel("Household password").fill(`${PASSWORD}-wrong`);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByLabel("Household password")).toHaveAttribute("aria-invalid", "true");
    await shot(page, "login-wrong-password", testInfo);
  });
});
