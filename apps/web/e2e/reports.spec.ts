import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

test("Reports breaks spending down by category, and a category opens exactly its records", async ({ page }) => {
  await page.goto("/reports");
  await expect(page).toHaveTitle("Reports · FinBoy");
  const where = page.getByRole("region", { name: "Where your money went" });
  const table = where.getByRole("table", { name: "Confirmed spending by category" });
  await expect(table.getByRole("row", { name: /Groceries/ })).toContainText("%");
  await table.getByRole("link", { name: "Groceries" }).click();
  await expect(page).toHaveURL(/\/transactions\?category=groceries&status=confirmed/);
  await expect(page.getByRole("list").getByText("Sample Grocer")).toBeVisible();
});

test("the last six months read as columns or as a table", async ({ page }) => {
  await page.goto("/reports?year=2026&month=10");
  const trend = page.getByRole("region", { name: "Month by month" });
  const table = trend.getByRole("table", { name: "Money in and money out, the last six months" });
  // Screen readers always have the table; the button puts it on screen in place of the chart.
  await expect(table.getByRole("row")).toHaveCount(7);
  await expect(table.getByRole("row", { name: /October 2026/ })).toContainText("₹62,000");
  await table.scrollIntoViewIfNeeded();
  await expect(table).not.toBeInViewport({ ratio: 0.5 });
  await expect(trend.getByText("Oct", { exact: true })).toBeVisible();
  await trend.getByRole("button", { name: "Show as table" }).click();
  await expect(trend.getByRole("button", { name: "Show chart" })).toHaveAttribute("aria-pressed", "true");
  await table.scrollIntoViewIfNeeded();
  await expect(table).toBeInViewport({ ratio: 0.5 });
  await expect(trend.getByText("Oct", { exact: true })).toHaveCount(0);
});

test("a month with nothing recorded says so, and the month control brings this month back", async ({ page }) => {
  await page.goto("/reports?year=2026&month=9");
  await expect(page.getByRole("heading", { name: "Nothing recorded for September 2026" })).toBeVisible();
  await page.getByRole("button", { name: "Add an entry" }).click();
  await expect(page.getByRole("dialog", { name: "Add money in or out" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByLabel("Month").selectOption({ label: "This month" });
  await expect(page).toHaveURL(/\/reports$/);
  await expect(page.getByRole("region", { name: "Where your money went" })).toBeVisible();
});

test("budgets show what is left and are added, removed and joined by a savings goal in place", async ({ page, api }) => {
  await page.goto("/reports");
  const budgets = page.getByRole("region", { name: "Budgets" });
  await expect(budgets.getByText("Food & dining")).toBeVisible();
  await expect(budgets.getByText(/ (left|over)$/)).toHaveCount(1);
  await budgets.getByRole("button", { name: "Add a budget" }).click();
  await budgets.getByLabel("Budget for").selectOption("groceries");
  await budgets.getByLabel("Each month (₹)").fill("2500");
  await budgets.getByRole("button", { name: "Save" }).click();
  await expect(budgets.getByRole("button", { name: "Change the Groceries budget" })).toBeVisible();
  const saved = api.requests.find((item) => item.method === "PATCH" && item.path.endsWith("/money/budgets"));
  expect(saved?.body).toEqual({ category: "groceries", limit_minor: 250000 });
  await budgets.getByRole("button", { name: "Change the Groceries budget" }).click();
  await budgets.getByRole("button", { name: "Remove" }).click();
  await expect(budgets.getByRole("button", { name: "Change the Groceries budget" })).toHaveCount(0);
  await budgets.getByRole("button", { name: "Set a monthly savings goal" }).click();
  await budgets.getByLabel("Keep each month (₹)").fill("5000");
  await budgets.getByRole("button", { name: "Save" }).click();
  await expect(budgets.getByText(/kept of ₹5,000/)).toBeVisible();
});
