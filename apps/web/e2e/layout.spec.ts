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
    ["/dashboard", "Ask about my money"],
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
  await page.getByLabel("Your question").focus();
  await expect(page.locator(".app-tabbar")).toBeHidden();
});

test("navigation labels meet WCAG AA contrast as rendered", async ({ page }) => {
  await page.goto("/dashboard");
  const samples = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('nav[aria-label="App navigation"] a')]
      .filter((link) => link.checkVisibility())
      .map((link) => {
        const label = link.querySelector<HTMLElement>("span:last-child") ?? link;
        const parse = (value: string) => (value.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
        return { text: label.textContent, color: parse(getComputedStyle(label).color), size: parseFloat(getComputedStyle(label).fontSize) };
      }),
  );
  expect(samples.length).toBeGreaterThan(0);
  // Worst case surface under the near-opaque bar: 94% white over the darkest ink (#14122b).
  const worstSurface = [0.94 * 255 + 0.06 * 20, 0.94 * 255 + 0.06 * 18, 0.94 * 255 + 0.06 * 43];
  for (const sample of samples) {
    expect(sample.size).toBeGreaterThanOrEqual(11);
    expect(contrast(sample.color, worstSurface), `${sample.text}`).toBeGreaterThanOrEqual(4.5);
  }
});

test("keyboard users can skip to content and see focus", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "hardware-keyboard path is checked at desktop width");
  await page.goto("/transactions");
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
    ["/dashboard", "Overview · FinBoy"],
    ["/transactions", "Transactions · FinBoy"],
    ["/review", "Review · FinBoy"],
    ["/assistant", "Ask FinBoy · FinBoy"],
    ["/sources", "Sources · FinBoy"],
    ["/privacy", "Privacy & data · FinBoy"],
  ] as const) {
    await page.goto(path);
    await expect(page).toHaveTitle(title);
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  }
});

test("offline shows an honest banner and recovers when back online", async ({ page, context }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: /Estimated unallocated/ })).toBeVisible();
  await context.setOffline(true);
  await expect(page.getByText("You're offline.")).toBeVisible();
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByRole("region", { name: /Estimated unallocated/ })).toBeVisible();
  await context.setOffline(false);
  await expect(page.getByText("You're offline.")).toBeHidden();
});

test("daily screens load no WebGL, and the landing page works without it", async ({ page }) => {
  const scripts: string[] = [];
  page.on("request", (request) => {
    if (request.resourceType() === "script") scripts.push(request.url());
  });
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: /Estimated unallocated/ })).toBeVisible();
  expect(await page.locator("canvas").count()).toBe(0);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/?graphics=off");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Your inbox");
  await expect(page.locator("canvas")).toHaveCount(0);
});
