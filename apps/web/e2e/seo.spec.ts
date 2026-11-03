import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

const publicPages = [
  "/", "/guides", "/features/whatsapp-expense-tracker", "/features/voice-expense-tracker",
  "/features/upi-expense-tracker", "/features/google-pay-statement-import",
  "/guides/download-google-pay-statement", "/guides/track-expenses-on-whatsapp",
  "/guides/track-cash-and-upi-expenses", "/guides/monthly-household-budget-india",
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
