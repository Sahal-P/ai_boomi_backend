import { FREE_FEATURES, PREMIUM_FEATURES } from "../src/lib/pricing.ts";
import { expect, test } from "./support/fixtures.ts";

const CHAT = "https://wa.me/919000000099?text=Hi%20FinBoy";
const PLACEHOLDERS = /Business details pending|Phone number pending|Address pending verification|Grievance officer pending/;

test.describe("while WhatsApp sign-up is open", () => {
  test.use({ scenario: { authRequired: true, signedIn: false, whatsapp: true } });

  test("every Start button opens FinBoy's chat; the code shows only on a computer", async ({ page }, testInfo) => {
    await page.goto("/?graphics=off");
    const starts = [
      page.getByRole("region", { name: /Keep track/ }),
      page.getByRole("banner"),
      page.getByRole("region", { name: /Say hi/ }),
    ].map((area) => area.getByRole("link", { name: "Start on WhatsApp" }));
    for (const start of starts) {
      await expect(start).toHaveAttribute("href", CHAT);
      await expect(start).toHaveAttribute("target", "_blank");
    }
    const code = page.getByRole("img", { name: "QR code that opens FinBoy's WhatsApp chat" });
    if (testInfo.project.name === "desktop") await expect(code).toBeVisible();
    else await expect(code).toHaveCount(0);
  });

  test("the chat answers every tap the way FinBoy does", async ({ page }) => {
    // Headless runs have no audio device: play() only reports that it started.
    await page.addInitScript(() => {
      HTMLMediaElement.prototype.play = function play() {
        return Promise.resolve();
      };
      HTMLMediaElement.prototype.pause = function pause() {};
    });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?graphics=off");
    const chat = page.getByRole("list", { name: "Example chat with FinBoy" });

    const voice = chat.getByRole("button", { name: "Play FinBoy's voice note" });
    await voice.click();
    await expect(voice).toHaveAttribute("aria-pressed", "true");
    await voice.click();
    await expect(voice).toHaveAttribute("aria-pressed", "false");

    const undoAll = chat.getByRole("button", { name: "Undo all" });
    await undoAll.click();
    await expect(chat.getByText("Removed 3 entries (₹190).")).toBeVisible();
    await expect(undoAll).toHaveAttribute("aria-disabled", "true");

    await chat.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(chat.getByText("Removed: ₹500 paid · milkman")).toBeVisible();
    await chat.getByRole("button", { name: "Put it back" }).click();
    await expect(chat.getByText(/Put back\.\s*✅ Saved: ₹500 paid/)).toBeVisible();

    await chat.getByRole("button", { name: "Amount", exact: true }).last().click();
    await expect(chat.getByText("Say or type the right amount. Like: 400")).toBeVisible();
    const field = page.getByRole("textbox", { name: "Message FinBoy the right amount" });
    await expect(field).toBeFocused();
    await field.fill("0");
    await field.press("Enter");
    await expect(chat.getByText("I didn't get the amount. Say or type just the amount, like: 400")).toBeVisible();
    await field.fill("400");
    await field.press("Enter");
    await expect(chat.getByText("Groceries: ₹2,200 of ₹6,000 this month")).toBeVisible();
    await expect(field).toHaveCount(0);

    await chat.getByRole("button", { name: "Category", exact: true }).last().click();
    const choose = chat.getByRole("button", { name: "Choose category" });
    await choose.click();
    const sheet = page.getByRole("dialog", { name: "Choose category" });
    await expect(sheet.getByRole("button", { name: "Food & dining" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(sheet).toHaveCount(0);
    await expect(choose).toBeFocused();
    await choose.click();
    await sheet.getByRole("button", { name: "Food & dining" }).click();
    await expect(chat.getByText("Changed to Food & dining. Next time, milkman goes there too.")).toBeVisible();

    await page.getByRole("button", { name: "Start again" }).click();
    await expect(chat.getByRole("listitem")).toHaveCount(5);
    await expect(chat.getByText("Removed 3 entries (₹190).")).toHaveCount(0);
  });

  test("the page shows the WhatsApp journey, the fixes and the same plans as /pricing", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?graphics=off");
    const chat = page.getByRole("list", { name: "Example chat with FinBoy" });
    await expect(chat.getByText("Saved 3 · ₹190")).toBeVisible();
    await expect(chat.getByText("Undo all")).toBeVisible();
    // Drawn the way WhatsApp draws it: its beige under FinBoy's doodles, your green bubbles and
    // FinBoy's white ones.
    const background = (element: Element) => getComputedStyle(element).backgroundColor;
    const screen = page.locator("[data-wa-screen]");
    expect(await screen.evaluate(background)).toBe("rgb(239, 234, 226)");
    expect(await screen.evaluate((element) => getComputedStyle(element).backgroundImage)).toContain(
      "/brand/chat-wallpaper.svg",
    );
    expect(await chat.locator("[data-from=you]").first().evaluate(background)).toBe("rgb(217, 253, 211)");
    expect(await chat.locator("[data-from=finboy]").first().evaluate(background)).toBe("rgb(255, 255, 255)");
    // WhatsApp never shows FinBoy's Premium pill: it sits in FinBoy's caption, outside the phone.
    await expect(chat.getByText("Premium")).toHaveCount(0);
    await expect(page.getByRole("figure").filter({ has: chat }).getByText("Premium", { exact: true })).toBeVisible();
    const fixes = page.getByRole("region", { name: /undone or fixed/ });
    for (const title of ["Undo", "Amount", "Category", "It asks first when unsure"]) {
      await expect(fixes.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }
    const plans = page.getByRole("region", { name: /Typing is free/ });
    for (const line of [...FREE_FEATURES, ...PREMIUM_FEATURES]) {
      await expect(plans.getByText(line, { exact: true })).toBeVisible();
    }
    await page.goto("/pricing");
    for (const line of [...FREE_FEATURES, ...PREMIUM_FEATURES]) {
      await expect(page.getByText(line, { exact: true })).toBeVisible();
    }
  });

  test("questions open in place", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/?graphics=off");
    const faq = page.getByRole("region", { name: "Before you say hi." });
    const answer = faq.getByText(/account, card and reference numbers are masked/);
    await expect(answer).toBeHidden();
    await faq.getByText("Does FinBoy read my SMS or connect to my bank?").click();
    await expect(answer).toBeVisible();
  });
});

test.describe("when FinBoy's API can't be reached", () => {
  test.use({ scenario: { authRequired: true, signedIn: false, whatsapp: true } });

  test("the main action falls back to the sign-in page", async ({ page }) => {
    await page.route("**/api/v1/auth/session", (route) => route.abort());
    await page.goto("/?graphics=off");
    const hero = page.getByRole("region", { name: /Keep track/ });
    await expect(hero.getByRole("link", { name: "Get started" })).toHaveAttribute("href", "/login");
    await expect(page.getByRole("link", { name: "Start on WhatsApp" })).toHaveCount(0);
    // The longer fallback label must not push the phone nav onto two lines.
    const nav = page.getByRole("banner");
    for (const name of ["Sign in", "Get started"]) {
      const lines = await nav.getByRole("link", { name, exact: true }).evaluate((link) => {
        // Lines of rendered text only: element boxes sit a little above their text.
        const tops = new Set<number>();
        const walker = document.createTreeWalker(link, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          const range = document.createRange();
          range.selectNodeContents(node);
          for (const rect of range.getClientRects()) if (rect.width > 0) tops.add(Math.round(rect.top));
        }
        return tops.size;
      });
      expect(lines, `${name} stays on one line`).toBe(1);
    }
  });
});

test("public pages make no Gmail, simulator or placeholder claims", async ({ page }) => {
  await page.goto("/?graphics=off");
  await expect(page.getByText(/Gmail|simulator/i)).toHaveCount(0);
  for (const path of ["/", "/contact", "/privacy-policy", "/terms", "/refund-policy", "/pricing"]) {
    await page.goto(path);
    await expect(page.locator("body")).not.toContainText(PLACEHOLDERS);
  }
  await page.goto("/contact");
  await expect(page.getByRole("link", { name: "support@finboy.io" }).first()).toBeVisible();
});
