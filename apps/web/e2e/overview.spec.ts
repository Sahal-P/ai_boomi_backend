import { ids } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

test("Home shows what is left, the three figures behind it and the working on request", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveTitle("Home · FinBoy");
  const hero = page.getByRole("region", { name: /Left this month/ });
  for (const name of [/^Money in/, /^Money out/, /^Bills due/]) await expect(hero.getByRole("link", { name }).first()).toBeVisible();
  await expect(hero.getByText("₹1,000 overdue · ₹1,000 unverified")).toBeHidden();
  await hero.getByText("How is this worked out?").click();
  await expect(hero.getByText("₹1,000 overdue · ₹1,000 unverified")).toBeVisible();
  await expect(hero.getByText(/Not included:/)).toBeVisible();
  // Review, an overdue bill, unread emails and records on hold; nothing about scans or coverage.
  await expect(page.getByRole("region", { name: "Needs your attention" }).getByRole("link")).toHaveCount(4);
  await expect(page.getByText(/Last successful scan|coverage/i)).toHaveCount(0);
});

test("an overdue bill stays taken off what's left until it is resolved through the dialog", async ({ page, api }) => {
  await page.goto("/dashboard");
  const bills = page.getByRole("region", { name: "Bills due" });
  await expect(bills.getByText("Overdue")).toBeVisible();
  await bills.locator(`[data-obligation-id="${ids.obligationOverdue}"]`).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("stays taken off what's left until you mark it paid or dismiss it")).toBeVisible();
  await expect(dialog.getByText("FinBoy isn't sure this bill is real")).toBeVisible();
  await dialog.getByRole("button", { name: "I've paid this" }).click();
  await expect(dialog.getByText("Marked as paid. It's no longer deducted.")).toBeVisible();
  const patch = api.requests.find((item) => item.method === "PATCH");
  expect(patch?.body).toMatchObject({ status: "paid", expected_version: expect.any(String) });
  await page.keyboard.press("Escape");
  await expect(page.locator(`[data-obligation-id="${ids.obligationOverdue}"]`)).toHaveCount(0);
});

test("the budgets snapshot leads to every budget in Reports", async ({ page }) => {
  await page.goto("/dashboard");
  const budgets = page.getByRole("region", { name: "Budgets" });
  await expect(budgets.getByText("Food & dining")).toBeVisible();
  await expect(budgets.getByRole("button", { name: /^Change the/ })).toHaveCount(0);
  await budgets.getByRole("link", { name: "All budgets" }).click();
  await expect(page).toHaveURL(/\/reports#budgets$/);
  await expect(page.getByRole("region", { name: "Budgets" }).getByRole("button", { name: "Add a budget" })).toBeVisible();
});

test("a failed bills panel never blanks Home", async ({ page, api }) => {
  api.failNext(/money\/obligations/, 503, "source_unavailable");
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: /Left this month/ })).toBeVisible();
  await expect(page.getByRole("region", { name: "Bills due" }).getByRole("alert")).toContainText("Bills couldn't be loaded");
});
