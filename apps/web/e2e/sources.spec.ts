import { ids } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

test("Sources manages the connected account with honest scan semantics", async ({ page, api }) => {
  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "Sources", level: 1 })).toBeVisible();
  await expect(page.getByText("ho***@example.test")).toBeVisible();
  await expect(page.getByText("Scans allowed")).toBeVisible();
  await expect(page.getByText("Partly scanned")).toBeVisible();
  await page.getByRole("button", { name: "Pause scans" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Scans are paused" })).toContainText("stops at its next safe point");
  await page.getByRole("button", { name: "Allow scans" }).click();
  await expect(page.getByText("Nothing was scanned yet — use Scan now")).toBeVisible();
  await page.getByRole("button", { name: "Scan now" }).click();
  await expect(page).toHaveURL(new RegExp(`/import/${ids.runningImport}$`));
  expect(api.requests.filter((item) => item.path.endsWith("/resume"))).toHaveLength(1);
  expect(api.requests.filter((item) => item.path.endsWith("/sync"))).toHaveLength(1);
});

test("old Connect links and the OAuth callback error land on Sources", async ({ page, api }) => {
  api.outcomes.push("denied");
  await page.goto("/connect");
  await expect(page).toHaveURL(/\/sources$/);
  await page.goto("/connect?error=consent_denied");
  await expect(page).toHaveURL(/\/sources\?error=consent_denied$/);
  await expect(page.getByRole("alert").filter({ hasText: "Gmail access was cancelled. Nothing was imported." })).toBeVisible();
});

test("a running import reports progress, survives a dropped poll and finishes with Review primary", async ({ page, api }) => {
  api.failNext(new RegExp(`/imports/${ids.runningImport}$`), 503, "source_unavailable", 1, "GET");
  await page.goto(`/import/${ids.runningImport}`);
  await expect(page.getByRole("button", { name: "Cancel import" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "4 new records need review" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Review 4 records" })).toBeVisible();
  await page.getByRole("button", { name: "Review 4 records" }).click();
  await expect(page).toHaveURL(/\/review/);
});

test("a partial Gmail import lists safe issue reasons and retries only failed emails", async ({ page, api }) => {
  await page.goto(`/import/${ids.partialImport}`);
  await expect(page.getByRole("heading", { name: "4 records need review · 2 emails couldn't be read" })).toBeVisible();
  await expect(page.getByText("Records waiting for review don't change your confirmed totals")).toBeVisible();
  await expect(page.getByText("Couldn't read the payment details")).toBeVisible();
  await page.getByRole("button", { name: "Retry 2 emails" }).click();
  await expect(page).not.toHaveURL(new RegExp(ids.partialImport));
  await expect(page.getByRole("heading", { name: /need review/ })).toBeVisible();
  const retry = api.requests.find((item) => item.path.endsWith("/retry"));
  expect(retry?.body).toMatchObject({ expected_version: expect.any(String) });
});

test("an interrupted upload asks for the original files and stages them before importing", async ({ page, api }) => {
  await page.goto(`/import/${ids.uploadInterrupted}`);
  await expect(page.getByRole("heading", { name: "Import was interrupted" })).toBeVisible();
  await page.getByRole("button", { name: "Select the original files again" }).click();
  const stager = page.getByRole("region", { name: "Select the original files again" });
  await expect(stager).toBeVisible();
  await stager.locator('input[type="file"]').setInputFiles([
    { name: "alert-1.eml", mimeType: "message/rfc822", buffer: Buffer.from("Subject: synthetic\r\n\r\nbody") },
    { name: "statement.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF synthetic") },
  ]);
  await expect(stager.getByText("Not an .eml email file")).toBeVisible();
  await expect(stager.getByRole("button", { name: "Retry with these files" })).toBeDisabled();
  await stager.getByRole("button", { name: "Remove statement.pdf" }).click();
  await expect(stager.getByRole("status")).toContainText("1 file selected");
  expect(api.requests.some((item) => item.path === "/api/v1/imports/eml")).toBe(false);
  await stager.getByRole("button", { name: "Retry with these files" }).click();
  await expect(page).toHaveURL(/\/import\/30000000-/);
  await expect(page).not.toHaveURL(new RegExp(ids.uploadInterrupted));
});

test("recent imports stay discoverable with stable links", async ({ page }) => {
  await page.goto("/sources");
  const history = page.getByRole("region", { name: "Recent imports" });
  await expect(history.getByRole("link")).toHaveCount(4);
  await history.getByRole("link").filter({ hasText: "Completed with issues" }).click();
  await expect(page).toHaveURL(new RegExp(`/import/${ids.partialImport}$`));
});
