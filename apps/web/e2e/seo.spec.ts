import { expect, test } from "./support/fixtures.ts";
import { readFile } from "node:fs/promises";

test.use({ scenario: { authRequired: false } });

const publicPages = [
  "/", "/guides", "/features/whatsapp-expense-tracker", "/features/voice-expense-tracker",
  "/features/upi-expense-tracker", "/features/google-pay-statement-import",
  "/guides/download-google-pay-statement", "/guides/track-expenses-on-whatsapp",
  "/guides/track-cash-and-upi-expenses", "/guides/monthly-household-budget-india",
  "/guides/choose-whatsapp-expense-tracker-india",
  "/tools/cash-upi-expense-diary",
];

test("public content has distinct canonical metadata and accessible headings", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const path of publicPages) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://finboy.io${path === "/" ? "" : path}`);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "index, follow");
    await expect(page.locator('meta[property="og:url"]')).toHaveAttribute("content", `https://finboy.io${path === "/" ? "" : path}`);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /.+/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (path === "/") await page.screenshot({ path: testInfo.outputPath("homepage.png") });
  }
});

test("sitemap contains public pages and private routes remain noindex", async ({ request }) => {
  const sitemap = await (await request.get("/sitemap.xml")).text();
  for (const path of publicPages) expect(sitemap).toContain(`https://finboy.io${path === "/" ? "" : path}`);
  for (const path of ["/dashboard", "/login", "/demo", "/pay", "/plan"]) {
    expect(sitemap).not.toContain(`<loc>https://finboy.io${path}</loc>`);
    const html = await (await request.get(path)).text();
    expect(html).toMatch(/name="robots" content="noindex, nofollow"/);
  }
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Sitemap: https://finboy.io/sitemap.xml");
  expect(robots).not.toContain("Disallow: /dashboard");
});

test("unknown content is 404, including inherited object property names", async ({ request }) => {
  for (const path of ["/features/not-a-feature", "/guides/not-a-guide", "/features/constructor", "/guides/toString"]) {
    expect((await request.get(path)).status()).toBe(404);
  }
});

test("guides include valid article and breadcrumb data without requiring JavaScript", async ({ browser, baseURL }) => {
  if (!baseURL) throw new Error("Missing test base URL");
  const context = await browser.newContext({ javaScriptEnabled: false, baseURL });
  try {
    const page = await context.newPage();
    await page.goto("/guides/download-google-pay-statement");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Google Pay");
    await expect(page.getByRole("link", { name: /official statement download/ })).toBeVisible();
    const scripts = await page.locator('script[type="application/ld+json"]').allTextContents();
    const schemas: unknown[] = scripts.map(value => JSON.parse(value));
    expect(schemas).toEqual(expect.arrayContaining([
      expect.objectContaining({ "@type": "Article" }), expect.objectContaining({ "@type": "BreadcrumbList" }),
    ]));
  } finally {
    await context.close();
  }
});

test("WhatsApp page shows the sample, plan details and contextual links", async ({ page }) => {
  await page.goto("/features/whatsapp-expense-tracker");
  await expect(page.getByRole("heading", { name: "Try a sample WhatsApp conversation" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Example chat with FinBoy" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Watch the 32-second captioned walkthrough" })).toHaveAttribute("href", "/video/whatsapp-example.mp4");
  await expect(page.getByText(/Text entries and typed questions are free/)).toBeVisible();
  await expect(page.getByRole("link", { name: "How to record UPI expenses" })).toHaveAttribute("href", "/features/upi-expense-tracker");
  await expect(page.getByRole("link", { name: "Read what FinBoy keeps and how to delete it" })).toHaveAttribute("href", "/privacy-policy");
});

test("updated guide has accurate dates and links to its source and feature", async ({ page, request }) => {
  await page.goto("/guides/download-google-pay-statement");
  await expect(page.getByRole("heading", { name: "Is this a bank statement?" })).toBeVisible();
  await expect(page.getByRole("link", { name: "How FinBoy imports Google Pay statements" })).toHaveAttribute("href", "/features/google-pay-statement-import");
  const article = await page.locator('script[type="application/ld+json"]').allTextContents();
  expect(article.map(value => JSON.parse(value))).toEqual(expect.arrayContaining([
    expect.objectContaining({ "@type": "Article", datePublished: "2026-11-04", dateModified: "2026-11-15" }),
  ]));
  const sitemap = await (await request.get("/sitemap.xml")).text();
  expect(sitemap).toMatch(/<loc>https:\/\/finboy\.io\/guides\/download-google-pay-statement<\/loc>\s*<lastmod>2026-11-15<\/lastmod>/);
  expect(sitemap).toMatch(/<loc>https:\/\/finboy\.io\/features\/voice-expense-tracker<\/loc>\s*<lastmod>2026-11-15<\/lastmod>/);
  expect(sitemap).toMatch(/<loc>https:\/\/finboy\.io\/guides\/monthly-household-budget-india<\/loc>\s*<lastmod>2026-11-04<\/lastmod>/);
});

test("public plan and privacy summaries distinguish typed Ask and saved chats", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Text entries and typed questions are free/)).toBeVisible();
  await expect(page.getByText(/Questions to Ask FinBoy and its answers are saved as chats/)).toBeVisible();
  await page.goto("/pricing");
  await expect(page.getByText("Ask FinBoy about your money, with answers from your own records")).toBeVisible();
  await expect(page.locator('meta[name="description"]')).not.toHaveAttribute("content", /Premium adds voice, Ask FinBoy/);
  await expect(page.getByText("Draft for legal review.")).toHaveCount(0);
});

test("voice, UPI and statement pages explain their different workflows", async ({ page }) => {
  await page.goto("/features/voice-expense-tracker");
  await expect(page.getByRole("heading", { name: "Three examples to try" })).toBeVisible();
  await expect(page.getByText(/questions to Ask FinBoy/i)).toBeVisible();
  await page.goto("/features/upi-expense-tracker");
  await expect(page.getByRole("heading", { name: "Check the reply and avoid double-counting" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download a Google Pay statement" })).toHaveAttribute("href", "/guides/download-google-pay-statement");
  await page.goto("/features/google-pay-statement-import");
  await expect(page.getByRole("heading", { name: "If FinBoy cannot import the file" })).toBeVisible();
  await expect(page.getByText(/not password-protected/)).toBeVisible();
});

test("comparison discloses the publisher and sources its competitor claims", async ({ page }) => {
  await page.goto("/guides/choose-whatsapp-expense-tracker-india");
  await expect(page.getByText(/FinBoy publishes this guide/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Expensebit: WhatsApp tracker details" })).toHaveAttribute("href", "https://expensebit.com/whatsapp-expense-tracker");
  const plans = page.getByRole("table");
  await expect(plans).toContainText("₹299/month");
  await expect(plans).toContainText("₹99/month");
  await expect(plans.getByRole("link", { name: "Xpensy" })).toHaveAttribute("href", "https://xpensy.in/");
  await expect(plans.getByRole("link", { name: "Expensebit" })).toHaveAttribute("href", "https://expensebit.com/pricing");
  const scripts = await page.locator('script[type="application/ld+json"]').allTextContents();
  expect(scripts.map(value => JSON.parse(value))).toEqual(expect.arrayContaining([
    expect.objectContaining({ "@type": "Article", datePublished: "2026-11-15", dateModified: "2026-11-15" }),
  ]));
});

test("free diary calculates offline, exports safe CSV and clears on reload", async ({ page }) => {
  await page.goto("/tools/cash-upi-expense-diary");
  await expect(page.getByText("No expenses added yet.")).toBeVisible();
  const leaked: string[] = [];
  page.on("request", (request) => {
    if (`${request.url()} ${request.postData() ?? ""}`.includes("=1+1")) leaked.push(request.url());
  });
  await page.context().setOffline(true);
  await page.getByLabel("Date (leave blank for today)").fill("2026-11-15");
  await page.getByLabel("What did you buy?").fill("Tea");
  await page.getByLabel("Amount in rupees").fill("20.50");
  await page.getByLabel("Paid with").selectOption("Cash");
  await page.getByRole("button", { name: "Add expense" }).click();
  await page.getByLabel("What did you buy?").fill("=1+1");
  await page.getByLabel("Amount in rupees").fill("120.05");
  await page.getByLabel("Paid with").selectOption("UPI");
  await page.getByRole("button", { name: "Add expense" }).click();
  await expect(page.getByText("₹140.55")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download CSV" }).click();
  const file = await downloadPromise;
  const path = await file.path();
  if (!path) throw new Error("CSV download was not available");
  const csv = await readFile(path, "utf8");
  expect(csv).toContain('"\'=1+1"');
  expect(csv).toContain('"120.05"');
  expect(leaked).toEqual([]);
  await page.getByRole("button", { name: "Remove Tea" }).click();
  await expect(page.getByText("₹20.50")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Entries (1)" })).toBeVisible();
  await page.context().setOffline(false);
  await page.reload();
  await expect(page.getByText("No expenses added yet.")).toBeVisible();
});
