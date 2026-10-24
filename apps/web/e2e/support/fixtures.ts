import { expect, test as base, type Page } from "@playwright/test";
import { FakeFinBoyApi, PASSWORD, type Scenario } from "./fake-api.ts";

/**
 * Every /api/v1 request from the page is answered by the TEST-ONLY contract double, at the
 * same origin as the app — the shape production uses with NEXT_PUBLIC_API_URL=/.
 */
export const test = base.extend<{ scenario: Scenario; api: FakeFinBoyApi; foreignApiCalls: string[] }>({
  scenario: [{}, { option: true }],
  foreignApiCalls: async ({ page, baseURL }, provide) => {
    const appOrigin = new URL(baseURL ?? "http://127.0.0.1:3032").origin;
    const foreign: string[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.startsWith("/api/v1") && url.origin !== appOrigin) foreign.push(url.origin);
    });
    await provide(foreign);
  },
  // Auto: every test talks to the double, even when it doesn't inspect it.
  api: [
    async ({ page, scenario, baseURL }, provide) => {
    const api = new FakeFinBoyApi(scenario);
    const appOrigin = new URL(baseURL ?? "http://127.0.0.1:3032").origin;
    await page.context().route("**/api/v1/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const headers = await request.allHeaders();
      let body: unknown = null;
      if ((headers["content-type"] ?? "").includes("application/json")) body = request.postDataJSON();
      const response = await api.handle(
        { method: request.method(), path: url.pathname, query: url.searchParams, body, origin: headers.origin ?? null },
        appOrigin,
      );
      await route.fulfill({
        status: response.status,
        headers: { "content-type": "application/json", "cache-control": "no-store", ...response.headers },
        body: response.raw ?? (response.body === undefined ? "" : JSON.stringify(response.body)),
      });
    });
    await provide(api);
    },
    { auto: true },
  ],
});

export { expect };

export async function signIn(page: Page, path = "/dashboard") {
  await page.goto(path);
  await expect(page).toHaveURL(/\/login\?next=/);
  await page.getByLabel("Household password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Fixed layers (nav, header, banners) that could cover content on phones. */
export async function fixedLayerBoxes(page: Page) {
  return page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>("body *")]
      .filter((node) => {
        const style = getComputedStyle(node);
        return style.position === "fixed" && style.display !== "none" && style.visibility !== "hidden" && node.offsetParent !== undefined;
      })
      .map((node) => node.getBoundingClientRect())
      .filter((box) => box.width > 0 && box.height > 0 && box.width < window.innerWidth * 1.01 && box.height < window.innerHeight * 0.5)
      .map((box) => ({ x: box.x, y: box.y, width: box.width, height: box.height })),
  );
}

export function intersects(a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}
