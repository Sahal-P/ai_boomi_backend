import type { Locator, Page } from "@playwright/test";
import { ids } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

/**
 * The glass theme's promises, checked on rendered pages rather than by eye: WCAG contrast for
 * every visible text, placeholder and form-control boundary against its composited background;
 * at most three blurred layers in view; legible fallbacks under each accessibility setting;
 * and thinking orbs that stay dark-ink, quiet for assistive tech and still when they should.
 */
test.use({ scenario: { authRequired: false } });

type Failure = { what: string; ratio: number; required: number; fg: number[]; bg: number[] };

async function settled(page: Page) {
  await expect(page.getByRole("dialog").or(page.getByRole("heading", { level: 1 })).first()).toBeVisible();
  await page.waitForLoadState("networkidle");
}

/** Every visible text, placeholder and form-control boundary below its WCAG 2.2 AA minimum. */
function contrastFailures(page: Page): Promise<Failure[]> {
  return page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("no 2D context");
    // The canvas resolves any CSS colour (oklch, color-mix, …) to sRGB.
    const rgba = (css: string): number[] => {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = "#000";
      ctx.fillStyle = css;
      ctx.fillRect(0, 0, 1, 1);
      const [r = 0, g = 0, b = 0, a = 0] = ctx.getImageData(0, 0, 1, 1).data;
      return [r, g, b, a / 255];
    };
    const over = (top: number[], bottom: number[]) => [0, 1, 2].map((i) => (top[i] ?? 0) * (top[3] ?? 1) + (bottom[i] ?? 0) * (1 - (top[3] ?? 1)));
    const luminance = (rgb: number[]) => {
      const [r = 0, g = 0, b = 0] = rgb.map((value) => {
        const channel = value / 255;
        return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const ratio = (a: number[], b: number[]) => {
      const [light = 0, dark = 0] = [luminance(a), luminance(b)].sort((x, y) => y - x);
      return (light + 0.05) / (dark + 0.05);
    };
    // Worst cases: the field's darkest point (its warm glow) and, under the floating phone
    // header and tab bar, the darkest content that can scroll beneath them.
    const fieldDarkest = [232, 211, 176];
    const ink = [14, 16, 19];

    function backdrop(element: Element): number[] {
      const box = element.getBoundingClientRect();
      const [x, y] = [box.left + box.width / 2, box.top + box.height / 2];
      const layers: number[][] = [];
      let floating = false;
      for (let node: Element | null = element; node; node = node.parentElement) {
        const style = getComputedStyle(node);
        const background = rgba(style.backgroundColor);
        if ((background[3] ?? 0) > 0) layers.push(background);
        if ((background[3] ?? 0) >= 0.999) break;
        if (style.position === "fixed" && node.classList.contains("glass")) floating = true;
        // Absolutely positioned earlier siblings paint beneath this node: the nav's ink capsule.
        let covered = false;
        for (let sibling = node.previousElementSibling; sibling && !covered; sibling = sibling.previousElementSibling) {
          const siblingStyle = getComputedStyle(sibling);
          const rect = sibling.getBoundingClientRect();
          if (siblingStyle.position !== "absolute" || x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) continue;
          const fill = rgba(siblingStyle.backgroundColor);
          if ((fill[3] ?? 0) > 0) layers.push(fill);
          covered = (fill[3] ?? 0) >= 0.999;
        }
        if (covered) break;
      }
      let base = floating ? ink : element.closest(".bg-field") ? fieldDarkest : rgba(getComputedStyle(document.body).backgroundColor);
      for (const layer of layers.reverse()) base = over(layer, base);
      return base;
    }
    const effectiveOpacity = (element: Element) => {
      let opacity = 1;
      for (let node: Element | null = element; node; node = node.parentElement) opacity *= Number(getComputedStyle(node).opacity);
      return opacity;
    };
    const visible = (element: Element) =>
      element.checkVisibility({ opacityProperty: true, visibilityProperty: true }) &&
      !element.closest("[aria-hidden='true'], .sr-only, option") &&
      element.getBoundingClientRect().width >= 2;

    const failures: Failure[] = [];
    const record = (what: string, fg: number[], bg: number[], required: number) => {
      const value = ratio(fg, bg);
      if (value < required) {
        failures.push({ what: what.slice(0, 70), ratio: Math.round(value * 100) / 100, required, fg: fg.map(Math.round), bg: bg.map(Math.round) });
      }
    };

    const seen = new Set<Element>();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const text = walker.currentNode.textContent?.trim();
      const element = walker.currentNode.parentElement;
      if (!text || !element || seen.has(element)) continue;
      seen.add(element);
      // Disabled controls are exempt; transient dimming (a refreshing list) is not the theme.
      if (!visible(element) || effectiveOpacity(element) < 0.95) continue;
      const style = getComputedStyle(element);
      const bg = backdrop(element);
      const size = parseFloat(style.fontSize);
      const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
      record(text, over(rgba(style.color), bg), bg, large ? 3 : 4.5);
    }
    for (const field of document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("input[placeholder], textarea[placeholder]")) {
      if (!visible(field) || field.value || field.disabled) continue;
      const bg = backdrop(field);
      record(`placeholder: ${field.placeholder}`, over(rgba(getComputedStyle(field, "::placeholder").color), bg), bg, 4.5);
    }
    const controls = "input:not([type=hidden], [type=checkbox], [type=radio], [type=file]), select, textarea, [role=checkbox], [role=radio]";
    for (const control of document.querySelectorAll<HTMLElement>(controls)) {
      if (!visible(control) || control.matches(":disabled") || !control.parentElement) continue;
      const style = getComputedStyle(control);
      const outside = backdrop(control.parentElement);
      const width = parseFloat(style.borderTopWidth);
      const border = width > 0 && style.borderTopStyle !== "none" ? over(rgba(style.borderTopColor), outside) : outside;
      record(`boundary: ${control.getAttribute("aria-label") ?? control.id ?? control.tagName}`, border, outside, 3);
    }
    return failures;
  });
}

function blurredLayersInView(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      [...document.querySelectorAll<HTMLElement>("body *")].filter((element) => {
        if (!element.checkVisibility() || getComputedStyle(element).backdropFilter === "none") return false;
        const box = element.getBoundingClientRect();
        return box.bottom > 0 && box.top < window.innerHeight && box.right > 0 && box.left < window.innerWidth;
      }).length,
  );
}

const ROUTES = [
  "/dashboard",
  "/transactions",
  "/transactions?q=no-such-merchant",
  `/transactions?selected=${ids.salary}`,
  "/review",
  `/review?selected=${ids.duplicate}`,
  "/assistant",
  "/sources",
  `/import/${ids.partialImport}`,
  "/privacy",
  "/demo",
  "/login",
  "/no-such-page",
];

for (const path of ROUTES) {
  test(`contrast and blur budget: ${path}`, async ({ page }) => {
    await page.goto(path);
    await settled(page);
    expect(await contrastFailures(page)).toEqual([]);
    expect(await blurredLayersInView(page)).toBeLessThanOrEqual(3);
  });
}

test("contrast and blur budget: the landing page", async ({ page }) => {
  // Reduced motion shows every scroll reveal, so every text is measured.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/?graphics=off");
  await settled(page);
  expect(await contrastFailures(page)).toEqual([]);
  expect(await blurredLayersInView(page)).toBeLessThanOrEqual(3);
});

test.describe("empty ledger", () => {
  test.use({ scenario: { authRequired: false, emptyLedger: true } });
  for (const path of ["/dashboard", "/transactions", "/review"]) {
    test(`yellow moments keep contrast: ${path}`, async ({ page }) => {
      await page.goto(path);
      await settled(page);
      await expect(page.locator(".moment").first()).toBeVisible();
      expect(await contrastFailures(page)).toEqual([]);
    });
  }
});

test("floating glass really blurs in Chromium", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "desktop", "the floating header is phone chrome");
  // With literal values the CSS minifier kept only -webkit-backdrop-filter, which Chrome ignores.
  await page.goto("/dashboard");
  await settled(page);
  expect(await page.locator("header.glass").evaluate((element) => getComputedStyle(element).backdropFilter)).toContain("blur(24px)");
});

test("Reduce Transparency removes every blur and makes glass opaque", async ({ page }) => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-transparency", value: "reduce" }] });
  await page.goto(`/transactions?selected=${ids.salary}`);
  await settled(page);
  expect(await page.evaluate(() => matchMedia("(prefers-reduced-transparency: reduce)").matches)).toBe(true);
  expect(await blurredLayersInView(page)).toBe(0);
  expect(await page.locator(".surface").first().evaluate((element) => getComputedStyle(element).backgroundColor)).toBe("rgb(236, 236, 238)");
  expect(await contrastFailures(page)).toEqual([]);
});

test("Increase Contrast darkens secondary ink and still passes", async ({ page }) => {
  await page.emulateMedia({ contrast: "more" });
  await page.goto("/dashboard");
  await settled(page);
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--ink-soft").trim())).toBe("#2e3136");
  expect(await contrastFailures(page)).toEqual([]);
});

test("forced colours keep every glass and yellow surface outlined", async ({ page }) => {
  await page.emulateMedia({ forcedColors: "active" });
  await page.goto("/dashboard");
  await settled(page);
  for (const selector of [".surface", ".solid-hero"]) {
    const border = await page.locator(selector).first().evaluate((element) => `${getComputedStyle(element).borderTopStyle} ${getComputedStyle(element).borderTopWidth}`);
    expect(border, selector).toBe("solid 1px");
  }
});

async function frame(orb: Locator) {
  return orb.evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL());
}

test("the resting orb is dark ink under a dark OS theme, hidden from assistive tech, and settles", async ({ page }) => {
  // FinBoy is light-only: a dark OS setting must not flip the orb to light dots.
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/assistant");
  const orb = page.locator('canvas[data-thinking-orb="breathing"]');
  // Orbs pause offscreen by design; on short phones this one starts below the fold.
  await orb.scrollIntoViewIfNeeded();
  await expect(orb).toBeVisible();
  await expect(orb).toHaveAttribute("aria-hidden", "true");
  const inkLevel = await orb.evaluate((canvas: HTMLCanvasElement) => {
    const data = canvas.getContext("2d")?.getImageData(0, 0, canvas.width, canvas.height).data ?? [];
    let count = 0;
    let sum = 0;
    for (let index = 0; index < data.length; index += 4) {
      if ((data[index + 3] ?? 0) < 128) continue;
      count += 1;
      sum += ((data[index] ?? 0) + (data[index + 1] ?? 0) + (data[index + 2] ?? 0)) / 3;
    }
    return count ? sum / count : 255;
  });
  // The library's light-mode ink is a mid grey (≈ rgb 100); its dark-mode dots are near white.
  expect(inkLevel).toBeLessThan(140);
  const first = await frame(orb);
  await page.waitForTimeout(400);
  expect(await frame(orb)).not.toBe(first);
  // Decorative motion stops within five seconds (WCAG 2.2.2).
  await page.waitForTimeout(5_200);
  const resting = await frame(orb);
  await page.waitForTimeout(400);
  expect(await frame(orb)).toBe(resting);
});

test("a pending answer shows the searching orb beside its text", async ({ page, api }) => {
  api.delay(/assistant\/ask/, 10_000);
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("How much did I spend this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const pending = page.getByRole("article", { name: /spend this month/ });
  await expect(pending.getByText("Thinking through your question…")).toBeVisible();
  await expect(pending.locator('canvas[data-thinking-orb="searching"]')).toHaveAttribute("aria-hidden", "true");
});

test("under reduced motion the orbs hold one still frame", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/assistant");
  const orb = page.locator('canvas[data-thinking-orb="breathing"]');
  await expect(orb).toBeVisible();
  const first = await frame(orb);
  await page.waitForTimeout(400);
  expect(await frame(orb)).toBe(first);
});
