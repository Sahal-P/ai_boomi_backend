import { ids } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

test("the estimate shows its dataset, freshness, exclusions and how it was calculated", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveTitle("Overview · FinBoy");
  const estimate = page.getByRole("region", { name: /Estimated unallocated/ });
  await expect(estimate.getByText("Last successful scan")).toBeVisible();
  await expect(estimate.getByText("partly scanned")).toBeVisible();
  await expect(estimate.getByRole("heading", { name: "How this is calculated" })).toBeVisible();
  await expect(estimate.getByText("₹1,000 overdue · ₹1,000 unverified")).toBeVisible();
  await expect(estimate.getByText(/Not included:/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Needs your attention" }).getByRole("link")).toHaveCount(4);
});

test("a category opens exactly its confirmed records for the period", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("region", { name: "Where it went" }).getByRole("link", { name: /Groceries/ }).click();
  await expect(page).toHaveURL(/\/transactions\?category=groceries&status=confirmed/);
  await expect(page.getByRole("list").getByText("Sample Grocer")).toBeVisible();
});

test("an overdue obligation stays deducted until it is resolved through the dialog", async ({ page, api }) => {
  await page.goto("/dashboard");
  const obligations = page.getByRole("region", { name: "Bills and obligations" });
  await expect(obligations.getByText("Overdue")).toBeVisible();
  await obligations.locator(`[data-obligation-id="${ids.obligationOverdue}"]`).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("stays deducted from your estimate until you mark it paid or dismiss it")).toBeVisible();
  await expect(dialog.getByText("FinBoy isn't sure this bill is real")).toBeVisible();
  await dialog.getByRole("button", { name: "I've paid this" }).click();
  await expect(dialog.getByText("Marked as paid. It's no longer deducted.")).toBeVisible();
  const patch = api.requests.find((item) => item.method === "PATCH");
  expect(patch?.body).toMatchObject({ status: "paid", expected_version: expect.any(String) });
  await page.keyboard.press("Escape");
  await expect(page.locator(`[data-obligation-id="${ids.obligationOverdue}"]`)).toHaveCount(0);
});

test("a simulation is bound to its amount and marked out of date when inputs or records change", async ({ page, api }) => {
  await page.goto("/dashboard");
  const panel = page.getByRole("region", { name: "What if I set money aside each month?" });
  await panel.getByLabel("Monthly amount (₹)").fill("5000");
  await panel.getByRole("button", { name: "Model cash flow" }).click();
  await expect(panel.getByText("Calculated for ₹5,000 a month")).toBeVisible();
  await panel.getByLabel("Monthly amount (₹)").fill("7000");
  await expect(panel.getByText("Out of date — you changed the amount")).toBeVisible();
  await panel.getByRole("button", { name: "Recalculate" }).click();
  await expect(panel.getByText("Calculated for ₹7,000 a month")).toBeVisible();
  api.bump();
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(panel.getByText("Out of date — your records changed since")).toBeVisible();
  api.failNext(/simulations/, 503, "source_unavailable");
  await panel.getByRole("button", { name: "Recalculate" }).click();
  await expect(panel.getByRole("alert")).toContainText("The result below is your last successful calculation.");
  await panel.getByLabel("Monthly amount (₹)").fill("abc");
  await panel.getByRole("button", { name: "Recalculate" }).click();
  await expect(panel.getByLabel("Monthly amount (₹)")).toHaveAttribute("aria-invalid", "true");
});

test("a failed secondary panel never blanks the primary overview", async ({ page, api }) => {
  api.failNext(/money\/obligations/, 503, "source_unavailable");
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: /Estimated unallocated/ })).toBeVisible();
  await expect(page.getByRole("region", { name: "Bills and obligations" }).getByRole("alert")).toContainText("Obligations couldn't be loaded");
});
