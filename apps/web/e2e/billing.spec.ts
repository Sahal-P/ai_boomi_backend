import type { Page, TestInfo } from "@playwright/test";
import { PLAN_NOW } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

// Subscription round (docs/subscription-round/contract.md). Plans, payments and links are the
// double's synthetic ones, on 25 Nov 2026; PayU's checkout page is intercepted and never reached.

const household = { authRequired: true, signedIn: true, selfServe: true, emptyLedger: true, connection: "none" } as const;

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date(PLAN_NOW));
});

/** Stands in for PayU's test checkout and keeps every form posted to it. */
async function interceptPayU(page: Page) {
  const posts: URLSearchParams[] = [];
  await page.route("https://test.payu.in/**", async (route) => {
    posts.push(new URLSearchParams(route.request().postData() ?? ""));
    await route.fulfill({ status: 200, contentType: "text/html", body: "<!doctype html><title>PayU test double</title><h1>PayU</h1>" });
  });
  return posts;
}

const upgradeSheet = (page: Page) => page.getByRole("dialog", { name: "₹299 / month" });

async function openAccountMenu(page: Page, testInfo: TestInfo) {
  const account =
    testInfo.project.name === "desktop"
      ? page.getByRole("complementary").getByRole("button", { name: /^Your household/ })
      : page.getByRole("button", { name: "Account and settings" });
  await account.click();
}

test.describe("on the Free plan", () => {
  test.use({ scenario: { ...household, plan: "free" } });

  test("a Premium control explains itself, and Pay goes straight to PayU with a signed form", async ({ page, api }, testInfo) => {
    const payu = await interceptPayU(page);
    await page.goto("/dashboard");
    await expect(page.getByText("You're on the free plan")).toBeVisible();
    await openAccountMenu(page, testInfo);
    await expect(page.getByRole("menuitem", { name: /^Plan\s*Free plan$/ })).toBeVisible();
    await page.keyboard.press("Escape");

    await page.getByRole("button", { name: "Add entry", exact: true }).click();
    const quickAdd = page.getByRole("dialog", { name: "Add money in or out" });
    await quickAdd.getByRole("button", { name: /^Say it/ }).click();
    await expect(quickAdd).toBeHidden();
    const sheet = upgradeSheet(page);
    await expect(sheet.getByText("Voice notes are part of Premium. Cancel any time.")).toBeVisible();
    // The WhatsApp number is PayU's phone; only the receipt email is asked for, once.
    await expect(sheet.getByLabel("Mobile number")).toHaveCount(0);
    const email = sheet.getByLabel("Email for receipts");
    await expect(email).toHaveAttribute("autocomplete", "email");
    await sheet.getByRole("button", { name: "Pay ₹299" }).click();
    expect(await email.evaluate((input: HTMLInputElement) => input.validity.valueMissing)).toBe(true);
    await email.fill("someone@example.test");
    await sheet.getByRole("button", { name: "Pay ₹299" }).click();
    await expect(page).toHaveURL("https://test.payu.in/_payment");
    expect(payu).toHaveLength(1);
    const form = payu[0] as URLSearchParams;
    expect(form.get("amount")).toBe("299.00");
    expect(form.get("email")).toBe("someone@example.test");
    expect(form.get("hash")).toMatch(/^[0-9a-f]{128}$/);
    expect([...form.keys()].some((name) => /salt/i.test(name))).toBe(false);
    const started = api.requests.filter((item) => item.path === "/api/v1/billing/checkout");
    expect(started.map((item) => item.body)).toEqual([{ email: "someone@example.test" }]);
  });

  test("Ask keeps the question while it explains Premium, and never sends it", async ({ page, api }) => {
    await page.goto("/assistant");
    await expect(page.getByText("Asking FinBoy is part of Premium.").first()).toBeVisible();
    await page.getByLabel("Your question").fill("How much did I spend this month?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(upgradeSheet(page).getByText("Asking FinBoy is part of Premium. Cancel any time.")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(upgradeSheet(page)).toBeHidden();
    await expect(page.getByLabel("Your question")).toHaveValue("How much did I spend this month?");
    expect(api.requests.some((item) => item.path === "/api/v1/assistant/ask")).toBe(false);
  });

  test("back from PayU, a paid month switches Premium on at once", async ({ page, api }) => {
    const payment = api.newPayment();
    await page.goto(`/plan?payment=${payment}`);
    const paid = page.getByRole("status").filter({ hasText: "You're on Premium" });
    await expect(paid.getByRole("heading", { name: "You're on Premium" })).toBeVisible();
    await expect(paid).toContainText("Paid through 25 Dec.");
    await expect(page.getByText("Premium until 25 Dec").first()).toBeVisible();
    await expect(page.getByRole("region", { name: "Payments" }).getByText(/UPI/)).toBeVisible();
    await paid.getByRole("button", { name: "Done" }).click();
    await expect(page).toHaveURL(/\/plan$/);
  });

  test("a payment the bank is still confirming says so, then switches on by itself", async ({ page, api }) => {
    const payment = api.newPayment();
    api.receipt = "pending";
    await page.goto(`/plan?payment=${payment}`);
    await expect(page.getByRole("heading", { name: "Confirming with your bank…" })).toBeVisible();
    await expect(page.getByText("You can leave this page — Premium switches on by itself.", { exact: false })).toBeVisible();
    api.receipt = "paid";
    await expect(page.getByRole("heading", { name: "You're on Premium" })).toBeVisible({ timeout: 10_000 });
  });

  test("a failed payment says no charge was made and offers to try again", async ({ page, api }) => {
    const payment = api.newPayment();
    api.receipt = "failed";
    await page.goto(`/plan?payment=${payment}`);
    const failed = page.getByRole("alert").filter({ hasText: "Payment didn't go through" });
    await expect(failed).toContainText("No charge was made.");
    await failed.getByRole("button", { name: "Try again" }).click();
    await expect(upgradeSheet(page)).toBeVisible();
    await expect(page).toHaveURL(/\/plan$/);
  });
});

test.describe("on the Free plan with statement import on", () => {
  test.use({ scenario: { ...household, plan: "free", statementImport: true } });

  test("Reports explains Premium where the import starts, with no detour to Sources", async ({ page }) => {
    await page.goto("/reports");
    await page.getByRole("button", { name: "Import a Google Pay statement" }).click();
    await expect(upgradeSheet(page).getByText("Importing statements is part of Premium. Cancel any time.")).toBeVisible();
    await expect(page).toHaveURL(/\/reports$/);
  });
});

test.describe("in the last week of the trial", () => {
  test.use({ scenario: { ...household, plan: "trial-ending" } });

  test("Home offers to keep Premium, and paying now never wastes trial days", async ({ page }, testInfo) => {
    await page.goto("/dashboard");
    await expect(page.getByText("Premium trial · 3 days left")).toBeVisible();
    await openAccountMenu(page, testInfo);
    await expect(page.getByRole("menuitem", { name: /^Plan\s*Trial · 3 days left$/ })).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Keep Premium" }).click();
    await expect(
      upgradeSheet(page).getByText("Your free trial continues until 28 Nov; your first paid month starts then."),
    ).toBeVisible();
  });
});

test.describe("early in the trial", () => {
  test.use({ scenario: { ...household, plan: "trial" } });

  test("Home stays quiet and every Premium control simply works", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Add what you spent today" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Keep Premium" })).toHaveCount(0);
    await page.goto("/assistant");
    await expect(page.getByText("Asking FinBoy is part of Premium.")).toHaveCount(0);
    await page.getByLabel("Your question").fill("How much did I spend this month?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByLabel("Your question")).toHaveValue("");
    await expect(upgradeSheet(page)).toBeHidden();
  });
});

test.describe("when a renewal fails", () => {
  test.use({ scenario: { ...household, plan: "grace" } });

  test("Home shows one amber chip that opens the payment sheet", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Payment didn't go through · Fix" }).click();
    await expect(upgradeSheet(page).getByRole("button", { name: "Pay ₹299" })).toBeVisible();
  });
});

test.describe("with AutoPay on", () => {
  test.use({ scenario: { ...household, plan: "autopay" } });

  test("AutoPay can be turned off, and Premium lasts to the end of the paid month", async ({ page, api }) => {
    await page.goto("/plan");
    await expect(page.getByText("Premium · AutoPay on")).toBeVisible();
    await expect(page.getByText(/₹299 is taken on 24 Dec/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Pay ₹299" })).toHaveCount(0);
    await page.getByRole("button", { name: "Turn off AutoPay" }).click();
    const confirm = page.getByRole("alertdialog", { name: "Turn off AutoPay?" });
    await expect(confirm).toContainText("Premium stays until 24 Dec");
    await confirm.getByRole("button", { name: "Turn off AutoPay" }).click();
    await expect(page.getByText("AutoPay is off. Premium lasts until 24 Dec; pay again any time.", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pay ₹299" })).toBeVisible();
    expect(api.requests.filter((item) => item.path === "/api/v1/billing/autopay/cancel")).toHaveLength(1);
  });
});

test.describe("a WhatsApp pay link", () => {
  test.use({ scenario: { authRequired: true, signedIn: false, plan: "trial" } });

  test("opens without sign-in in Hindi, keeps the token out of the address bar, and goes to PayU", async ({ page, api }) => {
    const payu = await interceptPayU(page);
    await page.goto("/pay#hi-link");
    await expect(page.locator("main")).toHaveAttribute("lang", "hi");
    await expect(page).toHaveURL(/\/pay$/);
    await expect(page.getByText("/ महीना")).toBeVisible();
    await page.getByLabel("रसीद के लिए ईमेल").fill("someone@example.test");
    await page.getByRole("button", { name: "₹299 भुगतान करें" }).click();
    await expect(page).toHaveURL("https://test.payu.in/_payment");
    expect(payu).toHaveLength(1);
    const started = api.requests.filter((item) => item.path === "/api/v1/billing/link/checkout");
    expect(started.map((item) => item.body)).toEqual([{ token: "hi-link", email: "someone@example.test" }]);
  });

  test("speaks Malayalam, and says plainly when a link has expired", async ({ page }) => {
    await page.goto("/pay#ml-link");
    await expect(page.locator("main")).toHaveAttribute("lang", "ml");
    await expect(page.getByRole("button", { name: "₹299 അടയ്ക്കൂ" })).toBeVisible();
    // A second link in the same tab changes only the fragment: the page starts again for it.
    await page.goto("/pay#old-link");
    // The language is unknown once a link has expired, so the message comes in all three.
    const expired = page.getByRole("main").getByRole("alert");
    await expect(expired).toContainText("This link has expired. Send any message to FinBoy on WhatsApp for a new one.");
    await expect(expired.locator('[lang="hi"]')).toContainText("यह लिंक पुराना हो गया है।");
    await expect(expired.locator('[lang="ml"]')).toContainText("ഈ ലിങ്കിന്റെ കാലാവധി കഴിഞ്ഞു.");
  });

  test("returns from PayU to the result in the chat's language", async ({ page, api }) => {
    const payment = api.newPayment();
    await page.goto("/pay#hi-link");
    await expect(page.getByText("/ महीना")).toBeVisible();
    await page.goto(`/pay?payment=${payment}`);
    await expect(page.getByRole("link", { name: "WhatsApp पर वापस जाएँ" }).first()).toHaveAttribute(
      "href",
      "https://wa.me/919000000099",
    );
  });
});

test.describe("billing off", () => {
  test.use({ scenario: { ...household } });

  test("no plan, no pills: everything is included", async ({ page }, testInfo) => {
    await page.goto("/plan");
    await expect(page.getByRole("heading", { name: "Everything is included" })).toBeVisible();
    await openAccountMenu(page, testInfo);
    await expect(page.getByRole("menuitem", { name: /^Plan/ })).toHaveCount(0);
  });
});

test("the pages PayU checks are public, linked from each other and fit a phone", async ({ page }) => {
  for (const [path, heading] of [
    ["/pricing", "Pricing"],
    ["/refund-policy", "Cancellation and refund policy"],
    ["/contact", "Contact"],
    ["/terms", "Terms"],
    ["/privacy-policy", "Privacy Policy"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
    const pages = page.getByRole("navigation", { name: "FinBoy pages" });
    for (const name of ["Pricing", "Terms", "Privacy Policy", "Refunds", "Contact"]) {
      await expect(pages.getByRole("link", { name, exact: true })).toBeVisible();
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.goto("/pricing");
  await expect(page.getByRole("region", { name: "Premium" })).toContainText("₹299 a month");
  await expect(page.getByRole("region", { name: "Free" })).toContainText("₹0");
});
