import { ids } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

async function openRecord(page: import("@playwright/test").Page, wide: boolean, name: string) {
  await page.getByRole("list", { name: "Records to review" }).getByRole("link", { name: new RegExp(name) }).click();
  const panel = wide ? page.getByRole("region", { name: "Decision" }) : page.getByRole("dialog");
  // Wait for the chosen record's evidence before interacting with its form.
  await expect(panel.getByRole("heading", { level: 2, name, exact: true })).toBeVisible();
  return panel;
}

test("the queue holds every unresolved month and filtered-empty never claims it's empty", async ({ page }) => {
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "4 records need review" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Records to review" }).getByText("Sample Pharmacy")).toBeVisible();
  await page.getByLabel("Search merchant or payer").fill("no such merchant");
  await expect(page.getByRole("heading", { name: "No records match these filters" })).toBeVisible();
  await expect(page.getByText("4 records still need review")).toBeVisible();
  await expect(page).toHaveURL(/q=no\+such\+merchant/);
  await page.getByRole("button", { name: "Clear filters" }).first().click();
  await expect(page.getByRole("list", { name: "Records to review" }).getByRole("link")).toHaveCount(4);
});

test("payment uncertainty is explained without a misleading percentage", async ({ page }, testInfo) => {
  await page.goto("/review");
  const panel = await openRecord(page, testInfo.project.name === "desktop", "Sample Marketplace");
  await expect(panel.getByText("An order or invoice email doesn't prove that money left your account.")).toBeVisible();
  await expect(panel.getByText("Payment not verified").first()).toBeVisible();
  await expect(panel.getByText(/%/)).toHaveCount(0);
});

test("save and confirm submits the edited value atomically, then undo restores it", async ({ page, api }, testInfo) => {
  const wide = testInfo.project.name === "desktop";
  await page.goto("/review");
  const panel = await openRecord(page, wide, "Sample Marketplace");
  await panel.getByLabel("Amount (₹)").fill("1799");
  await expect(panel.getByRole("button", { name: "Reject — not a real payment" })).toBeDisabled();
  await panel.getByRole("button", { name: "Save and confirm" }).click();
  await expect.poll(() => api.unresolved.length).toBe(3);
  const decision = api.requests.filter((item) => item.path.endsWith("/decisions")).at(-1);
  expect(decision?.body).toMatchObject({ action: "confirm", correction: { amount_minor: 179900 } });
  if (wide) await expect(page.getByRole("heading", { name: "3 records need review" })).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).first().click();
  await expect.poll(() => api.unresolved.length).toBe(4);
  if (wide) await expect(page.getByRole("heading", { name: "4 records need review" })).toBeVisible();
  expect(api.requests.some((item) => item.path.endsWith("/undo"))).toBe(true);
});

test("an evidence date after today still confirms; only a typed future date is refused", async ({ page, api }, testInfo) => {
  // The browser's today is before the record's 20 Oct evidence date (as with a scheduled debit).
  await page.clock.setFixedTime(new Date("2026-10-19T12:00:00+05:30"));
  await page.goto("/review");
  const panel = await openRecord(page, testInfo.project.name === "desktop", "Sample Marketplace");
  const date = panel.getByLabel("Date");
  await date.fill("2026-10-23");
  await panel.getByRole("button", { name: "Save and confirm" }).click();
  await expect(panel.getByText("The date can't be in the future.")).toBeVisible();
  await expect(date).toHaveAttribute("aria-invalid", "true");
  await panel.getByRole("button", { name: "Discard changes" }).click();
  await panel.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect.poll(() => api.unresolved.length).toBe(3);
  const decision = api.requests.filter((item) => item.path.endsWith("/decisions")).at(-1);
  expect(decision?.body).toMatchObject({ action: "confirm" });
  expect(decision?.body).not.toHaveProperty("correction.occurred_at");
});

test("a duplicate merges into a confirmed record from the independent candidate list", async ({ page, api }, testInfo) => {
  const wide = testInfo.project.name === "desktop";
  await page.goto("/review?q=Sample+Books");
  const panel = await openRecord(page, wide, "Sample Books");
  await expect(panel.getByText("Match (stays)")).toBeVisible();
  await expect(panel.getByText("Confirmed · suggested")).toBeVisible();
  await panel.getByRole("button", { name: "Preview merge" }).click();
  await expect(panel.getByText("this record's 1 source email moves to it")).toBeVisible();
  await panel.getByRole("button", { name: /Merge into/ }).click();
  await expect(page.getByText("Merged:")).toBeVisible();
  const merge = api.requests.filter((item) => item.path.endsWith("/decisions")).at(-1);
  expect(merge?.body).toMatchObject({ action: "merge", keep_id: ids.duplicateTarget });
  expect(api.requests.some((item) => item.path.endsWith("/merge-candidates"))).toBe(true);
});

test("a stale decision is refused and the edit survives", async ({ page, api }, testInfo) => {
  const wide = testInfo.project.name === "desktop";
  await page.goto("/review");
  const panel = await openRecord(page, wide, "Unknown merchant");
  await panel.getByLabel("Merchant or payer").fill("Sample Corner Shop");
  api.bump();
  await panel.getByRole("button", { name: "Save and confirm" }).click();
  await expect(panel.getByRole("alert")).toContainText("Nothing was overwritten");
  await expect(panel.getByLabel("Merchant or payer")).toHaveValue("Sample Corner Shop");
  await panel.getByRole("button", { name: "Load the latest version" }).click();
  await expect(panel.getByLabel("Merchant or payer")).toHaveValue("Sample Corner Shop");
  await panel.getByRole("button", { name: "Save and confirm" }).click();
  await expect(page.getByText("Confirmed:")).toBeVisible();
});

test("Escape asks before discarding an edited record on phones", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "desktop", "the desktop queue keeps the panel open");
  await page.goto("/review");
  const dialog = await openRecord(page, false, "Unknown merchant");
  await dialog.getByLabel("Merchant or payer").fill("Edited name");
  await page.keyboard.press("Escape");
  const confirm = page.getByRole("alertdialog", { name: "Discard your changes?" });
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: "Keep editing" }).click();
  await expect(confirm).toBeHidden();
  await expect(dialog.getByLabel("Merchant or payer")).toHaveValue("Edited name");
  await page.keyboard.press("Escape");
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: "Discard changes" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.locator(`[data-record-id="${ids.merchantUnclear}"]`)).toBeFocused();
});

test("leaving with an unsaved correction asks first", async ({ page }, testInfo) => {
  await page.goto("/review");
  const panel = await openRecord(page, testInfo.project.name === "desktop", "Unknown merchant");
  await panel.getByLabel("Merchant or payer").fill("Edited name");
  if (testInfo.project.name === "desktop") {
    await page.getByRole("navigation", { name: "App navigation" }).first().getByRole("link", { name: "Home" }).click();
    const confirm = page.getByRole("alertdialog", { name: "Leave without saving?" });
    await expect(confirm).toBeVisible();
    await confirm.getByRole("button", { name: "Keep editing" }).click();
    await expect(page).toHaveURL(/\/review/);
  } else {
    await expect(page.getByRole("dialog")).toBeVisible();
  }
});

test("keyboard: j and k move through the queue on desktop", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "single-key queue navigation is a desktop affordance");
  await page.goto("/review");
  await expect(page.getByRole("region", { name: "Decision" }).getByText("1 of 4")).toBeVisible();
  await page.keyboard.press("j");
  await expect(page.getByRole("region", { name: "Decision" }).getByText("2 of 4")).toBeVisible();
  await page.keyboard.press("k");
  await expect(page.getByRole("region", { name: "Decision" }).getByText("1 of 4")).toBeVisible();
  await page.keyboard.press("?");
  await expect(page.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeVisible();
});
