import { readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
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
  test.skip(before.startsWith("Nothing"), "the synthetic import produced no review items");
  // Phones open the decision as a dialog from the queue; desktop keeps it beside the queue.
  if (!wide) await page.getByRole("list", { name: "Records to review" }).getByRole("link").first().click();
  const panel = wide ? page.getByRole("region", { name: "Decision" }) : page.getByRole("dialog");
  // Wait for the decision form itself: a duplicate offers "keep both", other reasons Confirm.
  const decision = panel.getByRole("button", { name: /^(Confirm|Not a duplicate — keep both)$/ }).first();
  await expect(decision).toBeVisible();
  await decision.click();
  await expect(page.getByRole("button", { name: "Undo" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).first().click();
  if (!wide) await page.keyboard.press("Escape");
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

test("assistant: a supported question returns a paired, labelled answer or an honest failure", async ({ page }) => {
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("How much did I spend on food this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const turn = page.getByRole("article", { name: /food this month/ });
  await expect(turn.getByText(/From your household records|FinBoy needs one more detail|FinBoy couldn't answer that|Outside what FinBoy answers/)).toBeVisible({ timeout: 70_000 });
  test.info().annotations.push({ type: "assistant", description: (await turn.textContent())?.slice(0, 300) ?? "" });
});
