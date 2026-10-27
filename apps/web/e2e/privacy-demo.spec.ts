import { readFile } from "node:fs/promises";
import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

test("deletion shows its exact scope, backups and export before one confirmation", async ({ page, api }) => {
  await page.goto("/privacy");
  await page.getByRole("button", { name: "Preview deletion" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete imported records?" });
  await expect(dialog.getByText("10 records built from 14 imported emails")).toBeVisible();
  await expect(dialog.getByText("1 record also supported by emails from another source")).toBeVisible();
  await expect(dialog.getByText("up to 7 days after deletion")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Download my records (JSON)" })).toBeVisible();
  expect(api.requests.some((item) => item.path === "/api/v1/privacy/delete")).toBe(false);
  api.bump();
  await dialog.getByRole("button", { name: "Delete 10 records" }).click();
  await expect(dialog.getByRole("alert")).toContainText("The preview above has been refreshed");
  await dialog.getByRole("button", { name: "Delete 10 records" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Deleted 10 records" })).toBeVisible();
});

test("disconnect and deletion are separate choices", async ({ page, api }) => {
  await page.goto("/privacy");
  await page.getByRole("button", { name: "Disconnect" }).click();
  const dialog = page.getByRole("dialog", { name: "Disconnect Gmail?" });
  await expect(dialog.getByLabel("Keep them in my records")).toBeChecked();
  await dialog.getByRole("button", { name: "Disconnect Gmail" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Gmail disconnected. Your imported records were kept." })).toBeVisible();
  expect(api.requests.some((item) => item.path === "/api/v1/privacy/delete")).toBe(false);
  expect(api.requests.some((item) => item.method === "DELETE")).toBe(true);
});

test("export downloads only after an explicit click and contains no email content", async ({ page, api }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "downloads are checked once");
  await page.goto("/privacy");
  expect(api.requests.some((item) => item.path === "/api/v1/privacy/export")).toBe(false);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download my records (JSON)" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("finboy-export-2026-10-24.json");
  const content = JSON.parse(await readFile(await file.path(), "utf8")) as { dataset: string; schema_version: string };
  expect(content).toMatchObject({ dataset: "household", schema_version: "1.0" });
});

test("the sample is read-only, clearly labelled and never touches household endpoints", async ({ page, api }) => {
  await page.goto("/demo");
  await expect(page).toHaveTitle("Sample household · FinBoy");
  await expect(page.getByText("Sample data · read-only")).toBeVisible();
  await expect(page.getByRole("heading", { name: "A sample household" })).toBeVisible();
  await page.getByRole("button", { name: /Sample Books/ }).first().click();
  await expect(page.getByRole("dialog").getByText("Sample", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  const touched = api.requests.map((item) => `${item.method} ${item.path}`);
  expect(touched.every((item) => item === "GET /api/v1/demo" || item === "GET /api/v1/health")).toBe(true);
});

test("landing CTAs keep the visitor's intent: sample vs. one-tap sign-up", async ({ page }) => {
  await page.goto("/?graphics=off");
  await expect(page.getByRole("link", { name: "Explore sample data" }).first()).toHaveAttribute("href", "/demo");
  await expect(page.getByRole("link", { name: "Get started free" }).first()).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Get started", exact: true })).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: /Connect Gmail/ })).toHaveCount(0);
});
