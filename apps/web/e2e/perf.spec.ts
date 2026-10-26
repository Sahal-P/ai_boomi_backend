import { expect, test } from "./support/fixtures.ts";

/**
 * Opt-in scroll performance (E2E_PERF=1): the records list with the 230-record bulk fixture,
 * CPU slowed 4×, a scripted scroll down and back up. Frame times come from requestAnimationFrame
 * in the page; compare a build before and after a visual change on the same machine.
 */
test.skip(!process.env.E2E_PERF, "set E2E_PERF=1 to measure scroll frame times");
test.use({ scenario: { authRequired: false, bulk: 230 } });

test("scrolling the records list", async ({ page }, testInfo) => {
  await page.goto("/transactions?scope=all");
  await expect(page.locator("[data-record-id]").first()).toBeVisible();
  await page.waitForLoadState("networkidle");
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  const frames = await page.evaluate(async () => {
    const times: number[] = [];
    let last = 0;
    let running = true;
    const tick = (now: number) => {
      if (last) times.push(now - last);
      last = now;
      if (running) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    const step = Math.max(40, Math.round(window.innerHeight / 12));
    const frame = () => new Promise((resolve) => requestAnimationFrame(resolve));
    for (let index = 0; index < 120; index += 1) {
      window.scrollBy(0, step);
      await frame();
    }
    for (let index = 0; index < 120; index += 1) {
      window.scrollBy(0, -step);
      await frame();
    }
    running = false;
    return times;
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  const sorted = [...frames].sort((a, b) => a - b);
  const quantile = (q: number) => Math.round((sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))] ?? 0) * 10) / 10;
  const result = { frames: frames.length, p50: quantile(0.5), p95: quantile(0.95), max: quantile(1) };
  testInfo.annotations.push({ type: "frame-times", description: JSON.stringify(result) });
  console.log(`[perf] ${testInfo.project.name} ${JSON.stringify(result)}`);
  expect(frames.length).toBeGreaterThan(200);
});
