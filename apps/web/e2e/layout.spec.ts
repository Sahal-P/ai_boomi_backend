import { expect, fixedLayerBoxes, intersects, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

const contrast = (foreground: number[], background: number[]) => {
  const luminance = (rgb: number[]) => {
    const [r = 0, g = 0, b = 0] = rgb.map((value) => {
      const channel = value / 255;
      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return ((light ?? 0) + 0.05) / ((dark ?? 0) + 0.05);
};

test("primary actions are never covered by fixed layers on phones", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "desktop", "fixed phone chrome only");
  for (const [path, name] of [
    ["/sources", "Scan now"],
    ["/dashboard", "All budgets"],
    ["/assistant", "Ask"],
    ["/privacy", "Preview deletion"],
  ] as const) {
    await page.goto(path);
    const action = page.getByRole(path === "/dashboard" ? "link" : "button", { name, exact: true }).first();
    await action.scrollIntoViewIfNeeded();
    await expect(action).toBeVisible();
    const box = await action.boundingBox();
    if (!box) throw new Error(`no box for ${name}`);
    const layers = await fixedLayerBoxes(page);
    for (const layer of layers) expect(intersects(layer, box), `${name} on ${path} overlaps a fixed layer`).toBe(false);
  }
});

test("the tab bar steps aside while typing so the keyboard never hides the field", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "desktop", "phones only");
  await page.goto("/assistant");
  await expect(page.locator(".app-tabbar")).toBeVisible();
  // A real tap also waits for hydration and field stability before focusing.
  await page.getByLabel("Your question").click();
  await expect(page.getByLabel("Your question")).toBeFocused();
  await expect(page.locator(".app-tabbar")).toBeHidden();
});

test("Add entry opens quick add from every screen", async ({ page }) => {
  for (const path of ["/dashboard", "/transactions", "/review", "/reports", "/assistant", "/sources", "/privacy"]) {
    await page.goto(path);
    await page.getByRole("button", { name: "Add entry", exact: true }).click();
    const sheet = page.getByRole("dialog", { name: "Add money in or out" });
    await expect(sheet, path).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet, path).toBeHidden();
  }
});

test("navigation labels meet WCAG AA contrast as rendered", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("link", { name: "Home", exact: true })).toBeVisible();
  const samples = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('nav[aria-label="App navigation"] a')]
      .filter((link) => link.checkVisibility())
      .map((link) => {
        const label = link.querySelector<HTMLElement>("span:last-child") ?? link;
        const parse = (value: string) => (value.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
        return {
          text: label.textContent,
          active: link.getAttribute("aria-current") === "page",
          color: parse(getComputedStyle(label).color),
          size: parseFloat(getComputedStyle(label).fontSize),
        };
      }),
  );
  expect(samples.length).toBeGreaterThan(0);
  // The active label sits on the solid ink capsule (#0e1013). Every other label sits on the bar:
  // worst case 90% white (the lighter of the header and tab bar) over the darkest ink.
  const ink = [14, 16, 19];
  const worstSurface = ink.map((channel) => 0.9 * 255 + 0.1 * channel);
  for (const sample of samples) {
    expect(sample.size).toBeGreaterThanOrEqual(11);
    expect(contrast(sample.color, sample.active ? ink : worstSurface), `${sample.text}`).toBeGreaterThanOrEqual(4.5);
  }
});

test("keyboard users can skip to content and see focus", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "hardware-keyboard path is checked at desktop width");
  await page.goto("/transactions");
  await expect(page.getByRole("heading", { name: "Transactions", exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await page.keyboard.press("Tab");
  // Links use an outline; buttons and fields use a focus ring (box-shadow). Either must show.
  const focus = await page.evaluate(() => {
    const style = getComputedStyle(document.activeElement as Element);
    return { outline: style.outlineStyle, ring: style.boxShadow };
  });
  expect(focus.outline !== "none" || focus.ring !== "none").toBe(true);
});

test("every app route has a task title and one page heading", async ({ page }) => {
  for (const [path, title] of [
    ["/dashboard", "Home · FinBoy"],
    ["/transactions", "Transactions · FinBoy"],
    ["/review", "Review · FinBoy"],
    ["/reports", "Reports · FinBoy"],
    ["/assistant", "Ask FinBoy · FinBoy"],
    ["/sources", "Sources · FinBoy"],
    ["/privacy", "Privacy & data · FinBoy"],
  ] as const) {
    await page.goto(path);
    await expect(page).toHaveTitle(title);
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  }
});

test("no app screen scrolls sideways once its content is in", async ({ page }) => {
  for (const [path, ready] of [
    ["/dashboard", page.getByRole("region", { name: /Left this month/ })],
    ["/transactions", page.locator("[data-record-id]").first()],
    ["/review", page.getByRole("list", { name: "Records to review" })],
    ["/reports", page.getByRole("table", { name: "Money in and money out, the last six months" })],
    ["/assistant", page.getByLabel("Your question")],
    ["/sources", page.getByRole("heading", { level: 1 })],
    ["/privacy", page.getByRole("heading", { level: 1 })],
  ] as const) {
    await page.goto(path);
    await expect(ready).toBeAttached();
    // Against the layout viewport: a phone zooms out to fit overflow, which hides it from innerWidth.
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
    expect(fits, `${path} is wider than the screen`).toBe(true);
  }
});

test("offline shows an honest banner and recovers when back online", async ({ page, context }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: /Left this month/ })).toBeVisible();
  await context.setOffline(true);
  await expect(page.getByText("You're offline.")).toBeVisible();
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByRole("region", { name: /Left this month/ })).toBeVisible();
  await context.setOffline(false);
  await expect(page.getByText("You're offline.")).toBeHidden();
});

test("daily screens load no WebGL, and the landing page works without it", async ({ page }) => {
  const scripts: string[] = [];
  page.on("request", (request) => {
    if (request.resourceType() === "script") scripts.push(request.url());
  });
  // Thinking orbs are small 2D canvases, not WebGL; every other canvas is a 3D layer.
  const webgl = page.locator("canvas:not([data-thinking-orb])");
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: /Left this month/ })).toBeVisible();
  expect(await webgl.count()).toBe(0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/?graphics=off");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Your inbox");
  await expect(webgl).toHaveCount(0);
});
