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
  const samples = await page.evaluate(() => {
    const parse = (value: string) => {
      const [r = 0, g = 0, b = 0, a = 1] = (value.match(/[\d.]+/g) ?? []).map(Number);
      return [r, g, b, a];
    };
    const over = (top: number[], bottom: number[]) => [0, 1, 2].map((i) => (top[i] ?? 0) * (top[3] ?? 1) + (bottom[i] ?? 0) * (1 - (top[3] ?? 1)));
    // Liquid Glass: the darkest ink scrolled under the bar, dissolved by the scroll edge, then the
    // bar's own glass, then (for the selected item) Apple's platter.
    const ink = [14, 16, 19];
    const fieldDarkest = [232, 211, 176];
    return [...document.querySelectorAll<HTMLElement>('nav[aria-label="App navigation"] a')]
      .filter((link) => link.checkVisibility())
      .map((link) => {
        const label = link.querySelector<HTMLElement>("span:last-child") ?? link;
        const bar = link.closest("nav") as HTMLElement;
        const edge = bar.getAttribute("data-scroll-edge");
        const cover = edge ? parseFloat(getComputedStyle(document.documentElement).getPropertyValue(`--edge-cover-${edge}`)) : 1;
        let surface = over(parse(getComputedStyle(bar).backgroundColor), over([...fieldDarkest, cover], ink));
        const platter = link.querySelector<HTMLElement>(".lg-platter");
        if (platter) surface = over(parse(getComputedStyle(platter).backgroundColor), surface);
        return {
          text: label.textContent,
          color: parse(getComputedStyle(label).color),
          surface,
          size: parseFloat(getComputedStyle(label).fontSize),
        };
      });
  });
  expect(samples.length).toBeGreaterThan(0);
  for (const sample of samples) {
    expect(sample.size).toBeGreaterThanOrEqual(11);
    expect(contrast(sample.color.slice(0, 3), sample.surface), `${sample.text}`).toBeGreaterThanOrEqual(4.5);
  }
});

test("dragging across the tab bar lenses the tabs and opens the one released on", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "desktop", "the tab bar is phone chrome");
  await page.goto("/dashboard");
  const bar = page.locator('nav.lg[aria-label="App navigation"]');
  const from = await bar.getByRole("link", { name: "Home", exact: true }).boundingBox();
  const to = await bar.getByRole("link", { name: "Reports", exact: true }).boundingBox();
  if (!from || !to) throw new Error("no tab boxes");
  const y = from.y + from.height / 2;
  await page.mouse.move(from.x + from.width / 2, y);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width / 2, y, { steps: 10 });
  // The lens is decoration: hidden from assistive tech, gone once released.
  const lens = page.locator("[data-selection-lens]");
  await expect(lens).toBeVisible();
  await expect(lens).toHaveAttribute("aria-hidden", "true");
  await page.mouse.up();
  await expect(page).toHaveURL(/\/reports$/);
  await expect(lens).toHaveCount(0);
  await expect(bar.getByRole("link", { name: "Reports", exact: true })).toHaveAttribute("aria-current", "page");
});

test("the Clear · Tinted glass choice applies at once and is remembered", async ({ page }, testInfo) => {
  await page.goto("/dashboard");
  const account = testInfo.project.name === "desktop"
    ? page.getByRole("button", { name: /Your household/ })
    : page.getByRole("button", { name: "Account and settings" });
  await account.click();
  await page.getByRole("menuitemradio", { name: /Tinted/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-glass-look", "tinted");
  // The menu stays open so the change can be seen.
  await expect(page.getByRole("menuitemradio", { name: /Tinted/ })).toHaveAttribute("aria-checked", "true");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-glass-look", "tinted");
  await account.click();
  await page.getByRole("menuitemradio", { name: /Clear/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-glass-look", "clear");
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
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Keep track");
  await expect(webgl).toHaveCount(0);
});
