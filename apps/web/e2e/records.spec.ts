import { ids } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false, bulk: 230 } });

test("record 201 is reachable and the list says where you are", async ({ page }) => {
  await page.goto("/transactions?scope=all");
  await expect(page.getByRole("heading", { name: /^Showing 1–50 of 24\d for all time$/ })).toBeVisible();
  for (let index = 0; index < 4; index += 1) await page.getByRole("button", { name: "Next 50" }).click();
  await expect(page.getByRole("heading", { name: /^Showing 201–2\d\d of 24\d for all time$/ })).toBeVisible();
  await expect(page).toHaveURL(/offset=200/);
  await page.reload();
  await expect(page.getByRole("heading", { name: /^Showing 201–/ })).toBeVisible();
});

test("paging after a change reports the conflict instead of skipping records", async ({ page, api }) => {
  await page.goto("/transactions?scope=all");
  await expect(page.getByRole("heading", { name: /^Showing 1–50/ })).toBeVisible();
  api.bump();
  await page.getByRole("button", { name: "Next 50" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Your records changed while you were paging" })).toBeVisible();
  await page.getByRole("button", { name: "Go to the first page" }).click();
  await expect(page.getByRole("heading", { name: /^Showing 1–50/ })).toBeVisible();
});

test("rows say what kind of money event happened and how it counts", async ({ page }) => {
  await page.goto("/transactions?scope=all&q=Sample+Fuel");
  await expect(page.getByText("Not counted (payment failed)")).toBeVisible();
  await page.goto("/transactions?scope=all&kind=transfer");
  await expect(page.getByText("Transfer — not counted as spending")).toBeVisible();
  await page.goto("/transactions?scope=all&kind=refund");
  await expect(page.getByText("Reduces spending")).toBeVisible();
});

test("an answer citation opens its exact record and Back restores the answer", async ({ page, api }, testInfo) => {
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("How much did I spend at Sample Books this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByRole("article", { name: /Question: How much did I spend at Sample Books/ });
  await expect(answer.getByText("Spent at Sample Books")).toBeVisible();
  // The supporting records fold under the answer until asked for.
  await expect(answer.getByRole("link", { name: /Sample Books/ })).toHaveCount(0);
  await answer.getByText("showing 2 of 3 — a sample, not the full list").click();
  await answer.getByRole("link", { name: /Sample Books/ }).first().click();
  await expect(page).toHaveURL(new RegExp(`/transactions\\?selected=${ids.duplicateTarget}$`));
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Sample Books" })).toBeVisible();
  expect(api.requests.some((item) => item.method === "OUTCOME" && (item.body as { task?: string }).task === "evidence_opened")).toBe(true);
  await page.goBack();
  await expect(page).toHaveURL(/\/assistant$/);
  await expect(page.getByRole("article", { name: /Question: How much did I spend at Sample Books/ }).getByText("Spent at Sample Books")).toBeVisible();
  testInfo.annotations.push({ type: "evidence", description: "citation → exact record → Back keeps the answer (synthetic double)" });
});

test("closing a record from the list returns focus to its row", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "focus return is checked once with a keyboard");
  await page.goto("/transactions?scope=all&q=Sample+Cafe");
  const row = page.locator(`[data-record-id]`).first();
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(row).toBeFocused();
});
