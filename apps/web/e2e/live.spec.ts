import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

if (process.env.E2E_LIVE_API === "1") {
  const origin = new URL(process.env.E2E_API_ORIGIN ?? "https://127.0.0.1:8032");
  if (origin.hostname !== "127.0.0.1" || !["8031", "8032"].includes(origin.port)) {
    throw new Error("Live write journeys require the assigned loopback disposable API");
  }
}
import { expect, test } from "@playwright/test";

/**
 * LIVE journeys: no API double. The production build proxies /api/v1 to a real FinBoy API
 * (`E2E_LIVE_API=1`, `E2E_API_ORIGIN`, default https://127.0.0.1:8032 with its private certificate
 * in NODE_EXTRA_CA_CERTS) backed by a DISPOSABLE database. They upload the repository's synthetic
 * demo mailbox and make reversible decisions. Never point this at production.
 */
test.skip(process.env.E2E_LIVE_API !== "1", "needs a real disposable API behind the same-origin proxy");
test.describe.configure({ mode: "serial" });

const mailbox = new URL("../../api/fixtures/demo_mailbox/", import.meta.url);

test("upload: staged synthetic .eml files import through the proxy and show an outcome", async ({ page }) => {
  const files = (await readdir(mailbox)).filter((name) => name.endsWith(".eml")).sort();
  await page.goto("/sources");
  const stager = page.getByRole("region", { name: "Upload saved emails" });
  await stager.locator('input[type="file"]').setInputFiles(files.map((name) => fileURLToPath(new URL(name, mailbox))));
  await expect(stager.getByRole("status")).toContainText(`${files.length} files selected`);
  await stager.getByRole("button", { name: `Import ${files.length} emails` }).click();
  await expect(page).toHaveURL(/\/import\/[0-9a-f-]{36}$/);
  const outcome = page.locator("#outcome-title");
  await expect(outcome).not.toHaveText(/Importing|Getting ready/, { timeout: 90_000 });
  test.info().annotations.push({ type: "outcome", description: (await outcome.textContent()) ?? "" });
});

test("idempotency: re-uploading the same files adds nothing new", async ({ page }) => {
  const files = (await readdir(mailbox)).filter((name) => name.endsWith(".eml")).sort();
  await page.goto("/sources");
  const stager = page.getByRole("region", { name: "Upload saved emails" });
  await stager.locator('input[type="file"]').setInputFiles(files.map((name) => fileURLToPath(new URL(name, mailbox))));
  await stager.getByRole("button", { name: `Import ${files.length} emails` }).click();
  await expect(page).toHaveURL(/\/import\//);
  const outcome = page.locator("#outcome-title");
  await expect(outcome).not.toHaveText(/Importing|Getting ready/, { timeout: 90_000 });
  test.info().annotations.push({ type: "outcome", description: (await outcome.textContent()) ?? "" });
  await expect(page.locator("dt", { hasText: "New records added" }).locator("xpath=following-sibling::dd")).toHaveText("0");
});

test("overview: estimate, calculation, coverage and categories come from the API", async ({ page }) => {
  await page.goto("/dashboard");
  const estimate = page.getByRole("region", { name: /Estimated unallocated/ });
  await expect(estimate).toBeVisible();
  await expect(estimate.getByRole("heading", { name: "How this is calculated" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Where it went" }).getByRole("link").first()).toBeVisible();
  test.info().annotations.push({ type: "estimate", description: (await estimate.locator("p").nth(0).textContent()) ?? "" });
});

test("review: a decision is version-checked and undo restores the queue", async ({ page }, testInfo) => {
  const wide = testInfo.project.name === "desktop";
  await page.goto("/review");
  const heading = page.getByRole("heading", { name: /records? needs? review|Nothing needs review/ });
  await expect(heading).toBeVisible();
  const before = (await heading.textContent()) ?? "";
  expect(before).not.toMatch(/^Nothing/);
  // Phones open the decision as a dialog from the queue; desktop keeps it beside the queue.
  if (!wide) await page.getByRole("list", { name: "Records to review" }).getByRole("link").first().click();
  const panel = wide ? page.getByRole("region", { name: "Decision" }) : page.getByRole("dialog");
  if (!wide) await expect(page).toHaveURL(/selected=[0-9a-f-]{36}/);
  const selectedBefore = new URL(page.url()).searchParams.get("selected");
  // Wait for the decision form itself: a duplicate offers "keep both", other reasons Confirm.
  const decision = panel.getByRole("button", { name: /^(Confirm|Not a duplicate — keep both)$/ }).first();
  await expect(decision).toBeVisible();
  await decision.click();
  await expect(page.getByRole("button", { name: "Undo" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).first().click();
  if (!wide) {
    await expect(page).toHaveURL(new RegExp(`selected=${selectedBefore}`));
    await page.getByRole("button", { name: "Close record", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
  }
  await expect(page.getByRole("heading", { name: before })).toBeVisible();
});

test("records: paging metadata and an exact record link", async ({ page }) => {
  await page.goto("/transactions?scope=all");
  await expect(page.getByRole("heading", { name: /^Showing 1–\d+ of \d+ for all time$/ })).toBeVisible();
  const first = page.locator("[data-record-id]").first();
  const id = await first.getAttribute("data-record-id");
  await first.click();
  await expect(page).toHaveURL(new RegExp(`selected=${id}`));
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Evidence" })).toBeVisible();
});

test("privacy: deletion preview and explicit export without deleting anything", async ({ page }) => {
  await page.goto("/privacy");
  await page.getByRole("button", { name: "Preview deletion" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete imported records?" });
  await expect(dialog.getByText(/Will be permanently deleted/)).toBeVisible();
  await expect(dialog.getByText(/up to 7 days after deletion/)).toBeVisible();
  const download = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Download my records (JSON)" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.json$/);
  await dialog.getByRole("button", { name: "Cancel" }).click();
});

test("sample: /demo renders the read-only sample", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByText("Sample data · read-only")).toBeVisible();
  await expect(page.getByRole("region", { name: "Sample records" }).getByRole("button").first()).toBeVisible();
});

test("assistant: a supported question returns a deterministic successful answer with supporting evidence", async ({ page }) => {
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("How much did I spend on food this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const turn = page.getByRole("article", { name: /food this month/ });
  await expect(turn.getByText("From your household records", { exact: true })).toBeVisible({ timeout: 70_000 });
  await expect(turn.getByRole("heading", { name: /Supporting records/ })).toBeVisible();
  await expect(turn.getByText("₹6,610", { exact: true }).first()).toBeVisible();
  test.info().annotations.push({ type: "assistant", description: (await turn.textContent())?.slice(0, 300) ?? "" });
});


test("real obligations: an overdue bill stays deducted, can be resolved and reopened", async ({ page }) => {
  await page.goto("/dashboard");
  const obligation = page.locator("[data-obligation-id]").first();
  const id = await obligation.getAttribute("data-obligation-id");
  await obligation.click();
  const dialog = page.getByRole("dialog", { name: "Obligation details" });
  const due = dialog.getByLabel("Due date");
  const original = await due.inputValue();
  // The synthetic mailbox and disposable API use DEMO_TODAY=2026-10-24.
  const yesterday = "2026-10-23";
  await due.fill(yesterday);
  await dialog.getByRole("button", { name: "Save correction" }).click();
  await expect(dialog.getByText(/stays deducted from your estimate/)).toBeVisible();
  await dialog.getByRole("button", { name: "Close obligation" }).click();
  await expect(page.getByRole("region", { name: /Estimated unallocated/ }).getByText("₹14,780", { exact: true }).first()).toBeVisible();
  await page.locator(`[data-obligation-id="${id}"]`).click();
  await dialog.getByRole("button", { name: "I've paid this" }).click();
  await expect(dialog.getByText("Marked as paid. It's no longer deducted.")).toBeVisible();
  await dialog.getByRole("button", { name: "Reopen", exact: true }).click();
  await expect(dialog.getByText("Reopened. It's deducted again until resolved.")).toBeVisible();
  await due.fill(original);
  await dialog.getByRole("button", { name: "Save correction" }).click();
  await expect(dialog.getByText("Saved. The estimate uses the corrected obligation.")).toBeVisible();
  await dialog.getByRole("button", { name: "Close obligation" }).click();
});

test("real review: preview and merge into a confirmed record, then undo the deliberate mistake", async ({ page }, testInfo) => {
  const wide = testInfo.project.name === "desktop";
  await page.goto("/review?q=Amazon");
  await expect(page.getByRole("list", { name: "Records to review" }).getByRole("link")).toHaveCount(1);
  if (!wide) await page.getByRole("list", { name: "Records to review" }).getByRole("link").click();
  const panel = wide ? page.getByRole("region", { name: "Decision" }) : page.getByRole("dialog");
  if (!wide) await expect(page).toHaveURL(/selected=[0-9a-f-]{36}/);
  const selectedBefore = new URL(page.url()).searchParams.get("selected");
  await panel.getByRole("button", { name: "It's a duplicate…" }).click();
  const match = panel.locator("label").filter({ hasText: "Amazon" }).filter({ hasText: "Confirmed" }).first();
  await match.getByRole("radio").check();
  await panel.getByRole("button", { name: "Preview merge" }).click();
  await expect(panel.getByText("If you merge", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: /Merge into/ }).click();
  await page.getByRole("button", { name: "Undo", exact: true }).first().click();
  if (!wide) {
    await expect(page).toHaveURL(new RegExp(`selected=${selectedBefore}`));
    await page.getByRole("button", { name: "Close record", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
  }
  await expect(page.getByRole("list", { name: "Records to review" }).getByRole("link")).toHaveCount(1);
});

test("real history: record 201 is reachable across five imported source batches", async ({ page }) => {
  test.setTimeout(120_000);
  const template = await readFile(new URL("03-swiggy.eml", mailbox), "utf8");
  for (let offset = 0; offset < 205; offset += 50) {
    const files = Array.from({ length: Math.min(50, 205 - offset) }, (_, index) => {
      const number = String(offset + index).padStart(3, "0");
      const content = template
        .replaceAll("synthetic-swiggy", `uxpaging-${number}`)
        .replaceAll("BUNDL TECHNOLOGIES PVT LTD", `UXPAGING${number}`)
        .replaceAll("SYN-SWIGGY", `SYN-PAGING-${number}`)
        .replaceAll("2,210.00", `${3000 + offset + index}.00`)
        .replaceAll("03 Oct 2026", "03 Sep 2026")
        .replaceAll("03-10-26", "03-09-26");
      return { name: `synthetic-paging-${number}.eml`, mimeType: "message/rfc822", buffer: Buffer.from(content) };
    });
    await page.goto("/sources");
    const stager = page.getByRole("region", { name: "Upload saved emails" });
    await stager.locator('input[type="file"]').setInputFiles(files);
    await stager.getByRole("button", { name: `Import ${files.length} emails` }).click();
    await expect(page).toHaveURL(/\/import\//);
    await expect(page.locator("#outcome-title")).not.toHaveText(/Importing|Getting ready/, { timeout: 90_000 });
  }
  await page.goto("/transactions?scope=all&q=UXPAGING");
  await expect(page.getByRole("heading", { name: "Showing 1–50 of 205 for all time" })).toBeVisible();
  for (let index = 0; index < 4; index += 1) await page.getByRole("button", { name: "Next 50" }).click();
  await expect(page.getByRole("heading", { name: "Showing 201–205 of 205 for all time" })).toBeVisible();
  await expect(page).toHaveURL(/offset=200/);
  const record = page.locator("[data-record-id]").first();
  const id = await record.getAttribute("data-record-id");
  await record.click();
  await expect(page).toHaveURL(new RegExp(`selected=${id}`));
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Evidence" })).toBeVisible();
});
