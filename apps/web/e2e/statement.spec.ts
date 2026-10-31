import type { Page } from "@playwright/test";
import { expect, test } from "./support/fixtures.ts";

// Statement round (docs/statement-round/contract.md). Every statement here is the double's
// synthetic one: invented payees, bank and UPI IDs, Apr–Sep 2026.
test.use({ scenario: { authRequired: false, statementImport: true } });

const PDF = { name: "gpay_statement_20260401_20260930.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 synthetic") };
const fromStatement = (item: { source_modes: string[] }) => item.source_modes.includes("gpay_statement");

async function upload(page: Page, file: { name: string; mimeType: string; buffer: Buffer } = PDF) {
  await page.goto("/sources");
  const card = page.getByRole("region", { name: "Import a Google Pay statement" });
  await card.locator('input[type="file"]').setInputFiles(file);
  return card;
}

test("a statement is checked against Google Pay's totals, saved, and opens its six months", async ({ page, api }) => {
  await page.goto("/sources");
  const card = page.getByRole("region", { name: "Import a Google Pay statement" });
  await card.getByText("How do I get my statement?").click();
  await expect(card.getByText("Tap More (⋮) at the top right, then Get statement.")).toBeVisible();
  await card.locator('input[type="file"]').setInputFiles(PDF);
  await expect(page).toHaveURL(/\/import\/30000000-/);
  await expect(page.getByRole("heading", { name: "Saving your statement…" })).toBeVisible();
  const outcome = page.getByRole("heading", { name: "24 payments imported" });
  await expect(outcome).toBeVisible({ timeout: 15_000 });
  await expect(outcome).toBeFocused();
  const result = page.getByRole("region", { name: "24 payments imported" });
  await expect(result.getByText(/^Apr – Sept? 2026 · Sample Bank ••1234$/)).toBeVisible();
  await expect(result.getByText("23 new payments added")).toBeVisible();
  await expect(result.getByText("1 to check in To review")).toBeVisible();
  await expect(result.getByText("Matches Google Pay")).toHaveCount(2);
  await expect(result.getByText("₹48,181")).toBeVisible();
  await expect(result.getByText("₹14,320")).toBeVisible();
  expect(api.requests.filter((item) => item.method === "POST" && item.path === "/api/v1/imports/gpay")).toHaveLength(1);
  await expect(result.getByRole("link", { name: "Check 1" })).toHaveAttribute("href", "/review");

  await result.getByRole("link", { name: "See 6 months" }).click();
  await expect(page).toHaveURL(/\/reports\?from=2026-04&to=2026-09$/);
  await expect(page.getByLabel("Period")).toHaveValue("range:2026-04:2026-09");
  await expect(page.getByRole("listitem").filter({ hasText: "Confirmed spending over 6 months" })).toContainText("₹48,181");
});

test("a statement's months show who you pay, regular payments, money with people and small payments", async ({ page, api }) => {
  api.seedStatement();
  // The patterns load on their own: when they fail, the rest of Reports still shows.
  api.failNext(/\/money\/insights$/, 503, "source_unavailable");
  await page.goto("/reports?from=2026-04&to=2026-09");
  await expect(page.getByLabel("Period")).toHaveValue("range:2026-04:2026-09");
  await expect(page.getByText("₹34,963 of your spending is still “Other”.")).toBeVisible();
  const failed = page.getByRole("alert").filter({ hasText: "Payees and patterns couldn't be loaded" });
  await expect(failed).toBeVisible();
  await expect(page.getByRole("region", { name: "Where your money went" })).toBeVisible();
  await failed.getByRole("button", { name: "Try again" }).click();

  const payees = page.getByRole("region", { name: "Who you pay most" });
  await expect(payees.getByRole("table", { name: "Who you paid most" }).getByRole("row", { name: /Sample Card/ })).toContainText(
    /₹14,505.*30%.*3 times/,
  );
  await expect(payees.getByRole("table", { name: "Who paid you most" }).getByRole("row", { name: /Ravi Kumar/ })).toContainText("₹12,320");
  await expect(payees.getByRole("link", { name: /Ravi Kumar/ }).last()).toContainText("₹12,400");

  const regular = page.getByRole("region", { name: "Regular payments" });
  await expect(regular).toContainText("About ₹5,579.50 a month");
  await expect(regular.getByRole("link").first()).toContainText("Sample Card");
  await expect(regular.getByRole("link", { name: /Sample Broadband/ })).toContainText("Utilities · 4 of the last 6 months");

  const people = page.getByRole("region", { name: "Money with people" });
  await expect(people.getByRole("link", { name: /Ravi Kumar/ })).toContainText("Sent ₹12,400 · got back ₹12,320");
  await expect(people).toContainText("You sent ₹80 more");

  const small = page.getByRole("region", { name: "Small payments" });
  await expect(small).toContainText("₹18 a month under ₹200");
  await expect(small).toContainText("9 payments — 41% of your payments but <1% of your money.");
  await expect(small.getByRole("link", { name: /Corner Tea/ })).toContainText("9 times · ₹108");

  // A payee's name opens exactly its payments in the same months.
  await payees.getByRole("table", { name: "Who you paid most" }).getByRole("link", { name: "Sample Card" }).click();
  await expect(page).toHaveURL(/\/transactions\?q=Sample%20Card&status=confirmed&from=2026-04&to=2026-09$/);
  await expect(page.locator("[data-record-id]")).toHaveCount(3);
});

test("Sort payees gives every payment to a payee a category, and Reports follows", async ({ page, api }) => {
  const id = api.seedStatement();
  await page.goto(`/import/${id}`);
  await page.getByRole("link", { name: "Sort payees" }).click();
  await expect(page).toHaveURL(/\/reports\?from=2026-04&to=2026-09&sort=payees$/);
  const sheet = page.getByRole("dialog", { name: "Sort payees" });
  await expect(sheet.getByText("27% of spending sorted")).toBeVisible();
  const meter = sheet.getByRole("progressbar", { name: "Spending sorted into categories" });
  await expect(meter).toHaveAttribute("aria-valuenow", "27");
  const list = sheet.getByRole("list", { name: "Payees to sort" });
  await expect(list.getByRole("listitem")).toHaveCount(4);
  await expect(list.getByRole("listitem").first()).toContainText("Sample Card3 payments · ₹14,505");
  await sheet.getByLabel("Asha Stores").selectOption("groceries");
  await expect(sheet.getByText("44% of spending sorted")).toBeVisible();
  await expect(meter).toHaveAttribute("aria-valuenow", "44");
  await expect(list.getByRole("listitem").filter({ hasText: "Asha Stores" }).getByLabel("Sorted")).toBeVisible();
  const sorted = api.requests.find((item) => item.path === "/api/v1/money/payees/category");
  expect(sorted?.body).toEqual({ name: "Asha Stores", category: "groceries", expected_version: expect.any(String) });
  expect(api.transactions.filter((item) => item.merchant === "Asha Stores").map((item) => item.category)).toEqual(["groceries", "groceries", "groceries"]);

  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(page).toHaveURL(/\/reports\?from=2026-04&to=2026-09$/);
  await expect(page.getByText("₹27,013 of your spending is still “Other”.")).toBeVisible();
  const where = page.getByRole("table", { name: "Confirmed spending by category" });
  await expect(where.getByRole("row", { name: /Groceries/ })).toContainText("₹8,450");
});

test("a statement that doesn't add up saves nothing and shows both totals", async ({ page, api }) => {
  api.statementOutcome = "mismatch";
  await upload(page);
  const title = "This statement didn't add up, so nothing was imported";
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  const result = page.getByRole("region", { name: title });
  await expect(result.getByText("Google Pay says ₹60,681")).toBeVisible();
  await expect(result.getByText("Matches Google Pay")).toHaveCount(1);
  await expect(result.getByRole("link", { name: /See \d+ months/ })).toHaveCount(0);
  expect(api.transactions.some(fromStatement)).toBe(false);
  await result.getByRole("link", { name: "Choose the PDF again" }).click();
  await expect(page).toHaveURL(/\/sources#statement$/);
});

test("a file that isn't a readable Google Pay statement is turned away with nothing imported", async ({ page, api }) => {
  const card = await upload(page, { name: "statement.png", mimeType: "image/png", buffer: Buffer.from("synthetic") });
  await expect(card.getByRole("alert")).toContainText("That isn't a PDF.");
  expect(api.requests.some((item) => item.path === "/api/v1/imports/gpay")).toBe(false);
  const cases = [
    [422, "not_gpay_statement", "This isn't a Google Pay statement. Nothing was imported."],
    [422, "statement_locked", "This statement is password-protected."],
    [422, "statement_unreadable", "FinBoy couldn't read every row of this statement"],
    [409, "statement_already_imported", "This statement is already in FinBoy. Nothing was added twice."],
    [409, "import_busy", "Another import is still running."],
    [413, "upload_limit", "This statement is too long for one import."],
  ] as const;
  for (const [status, code, copy] of cases) {
    api.failNext(/\/imports\/gpay$/, status, code);
    await card.locator('input[type="file"]').setInputFiles(PDF);
    await expect(card.getByRole("alert")).toContainText(copy);
    await expect(card.getByRole("alert")).toContainText("Your statement wasn't imported");
  }
  await expect(page).toHaveURL(/\/sources$/);
  expect(api.imports.size).toBe(4);
});

test("an upload while offline says nothing changed", async ({ page, api }) => {
  await page.goto("/sources");
  const card = page.getByRole("region", { name: "Import a Google Pay statement" });
  // Only once the page has loaded: going offline mid-load fails the page itself. Routed requests
  // still reach the double while offline, so the upload is failed as a lost connection would.
  await expect(card.getByRole("button", { name: "Choose statement PDF" })).toBeVisible();
  await page.route("**/api/v1/imports/gpay", (route) => route.abort("internetdisconnected"));
  await page.context().setOffline(true);
  await card.locator('input[type="file"]').setInputFiles(PDF);
  await expect(card.getByRole("alert")).toContainText("You're offline. Nothing changed.");
  await page.context().setOffline(false);
  expect(api.imports.size).toBe(4);
});

test("removing a statement takes out what it added, and it can be imported again", async ({ page, api }) => {
  const id = api.seedStatement();
  await page.goto(`/import/${id}`);
  await page.getByRole("button", { name: "Remove this import" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Remove this statement?" });
  await expect(dialog).toContainText("24 records this statement added will be removed, with any changes you made to them.");
  await dialog.getByRole("button", { name: "Keep it" }).click();
  await expect(dialog).toBeHidden();
  expect(api.transactions.filter(fromStatement)).toHaveLength(24);

  await page.getByRole("button", { name: "Remove this import" }).click();
  await dialog.getByRole("button", { name: "Remove statement" }).click();
  await expect(page.getByRole("heading", { name: "This statement was removed" })).toBeVisible();
  expect(api.transactions.some(fromStatement)).toBe(false);
  expect(api.requests.find((item) => item.path === `/api/v1/imports/${id}/remove`)?.body).toEqual({ expected_version: expect.any(String) });
  await page.getByRole("link", { name: "Import it again" }).click();
  await expect(page).toHaveURL(/\/sources#statement$/);
  const removed = page.getByRole("region", { name: "Recent imports" }).getByRole("link").first();
  await expect(removed).toContainText("Removed");
  await expect(removed).not.toContainText(" new");
});

test("a statement record shows what Google Pay printed, and statement records filter by source", async ({ page, api }) => {
  api.seedStatement();
  const broadband = api.transactions.find((item) => item.merchant === "Sample Broadband");
  await page.goto(`/transactions?selected=${broadband?.id ?? ""}`);
  const record = page.getByRole("dialog");
  await expect(record.getByRole("heading", { name: "Sample Broadband" })).toBeVisible();
  await expect(record.getByText("Your Google Pay statement", { exact: true })).toBeVisible();
  await expect(record.getByText("Payment listed in your Google Pay statement")).toBeVisible();
  await expect(record.getByText("Details in the statement")).toBeVisible();
  await expect(record.getByText("Google Pay statement · page 3, row 2 · read by a fixed rule")).toBeVisible();
  await expect(record.getByText("“Paid to Sample Broadband”")).toBeVisible();
  await expect(record.getByText("260605000006")).toBeVisible();
  await expect(record.getByText("Sample Bank ••1234", { exact: true })).toBeVisible();

  await page.goto("/transactions?scope=all&source=gpay_statement");
  await expect(page.locator("[data-record-id]")).toHaveCount(24);
  await expect(page.getByText("Sample Grocer")).toHaveCount(0);
});

test("an empty period points to statement import", async ({ page }) => {
  await page.goto("/reports?year=2026&month=8");
  await expect(page.getByRole("heading", { name: "Nothing recorded for August 2026" })).toBeVisible();
  await page.getByRole("link", { name: "Import a Google Pay statement" }).click();
  await expect(page).toHaveURL(/\/sources#statement$/);
  await expect(page.getByRole("region", { name: "Import a Google Pay statement" })).toBeInViewport();
});

test.describe("while statement import is off", () => {
  test.use({ scenario: { authRequired: false } });

  test("Sources and Reports don't offer it", async ({ page }) => {
    await page.goto("/sources");
    await expect(page.getByText("ho***@example.test")).toBeVisible();
    await expect(page.getByRole("region", { name: "Import a Google Pay statement" })).toHaveCount(0);
    await page.goto("/reports?year=2026&month=8");
    await expect(page.getByRole("heading", { name: "Nothing recorded for August 2026" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Import a Google Pay statement" })).toHaveCount(0);
  });
});
