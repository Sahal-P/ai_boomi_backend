import { LOGIN_CODE } from "./support/fake-api.ts";
import { expect, test } from "./support/fixtures.ts";

test.describe("one-tap sign-in with WhatsApp", () => {
  test.use({ scenario: { authRequired: true, signedIn: false, whatsapp: true } });

  test.beforeEach(async ({ page }) => {
    // wa.me is never contacted from tests: the opened tab gets an empty page.
    await page.context().route("https://wa.me/**", (route) => route.fulfill({ body: "", contentType: "text/html" }));
  });

  test("tap, send, ✅ on the phone, and this page signs in by itself", async ({ page, api }, testInfo) => {
    await page.goto("/review");
    await expect(page).toHaveURL(/\/login\?next=%2Freview$/);
    const button = page.getByRole("link", { name: "Continue with WhatsApp" });
    await expect(button).toHaveAttribute("href", `https://wa.me/919000000099?text=FinBoy%20login%20code%20${LOGIN_CODE}`);
    await expect(button).toHaveAttribute("target", "_blank");
    // Computers get a QR code of the same link; phones just tap.
    const scan = page.getByText("On a computer? Scan with your phone");
    if (testInfo.project.name === "desktop") {
      await expect(page.getByRole("img", { name: "QR code that opens FinBoy's WhatsApp chat" })).toBeVisible();
      await expect(page.getByText(LOGIN_CODE)).toBeVisible();
    } else {
      await expect(scan).toBeHidden();
    }
    await expect(page.getByLabel("Household password")).toBeHidden();

    const tab = page.waitForEvent("popup");
    await button.click();
    await (await tab).close();
    await expect(page.getByRole("status").filter({ hasText: "Waiting for you on WhatsApp" })).toBeVisible();
    api.answerWhatsApp("yes");
    await expect(page).toHaveURL(/\/review$/, { timeout: 10_000 });
    expect(api.signedIn).toBe(true);
    expect(api.requests.filter((item) => item.path === "/api/v1/auth/whatsapp/complete")).toHaveLength(1);
  });

  test("No on WhatsApp signs nobody in and offers a fresh start", async ({ page, api }) => {
    await page.goto("/login");
    await expect(page.getByRole("link", { name: "Continue with WhatsApp" })).toBeVisible();
    api.answerWhatsApp("no");
    await expect(page.getByText("You tapped No on WhatsApp")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Start again" }).click();
    await expect(page.getByRole("link", { name: "Continue with WhatsApp" })).toBeVisible();
    expect(api.signedIn).toBe(false);
  });

  test("legal links and the sample are one tap away", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("link", { name: "Privacy Policy" }).click();
    await expect(page.getByRole("heading", { name: "Privacy Policy", level: 1 })).toBeVisible();
    await expect(page.getByText("Your WhatsApp messages, voice notes, photos or screenshots")).toBeVisible();
    await page.goto("/terms");
    await expect(page.getByRole("heading", { name: "Terms", level: 1 })).toBeVisible();
  });
});

test.describe("when FinBoy is full", () => {
  test.use({ scenario: { authRequired: true, signedIn: false, whatsapp: true, signupOpen: false } });

  test("existing households are told they can still sign in", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("New accounts are full for now. Already have one? Sign in as usual.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Continue with WhatsApp" })).toBeVisible();
  });
});

test.describe("quick add for a new household", () => {
  test.use({ scenario: { authRequired: true, signedIn: true, emptyLedger: true, selfServe: true, connection: "none" } });

  test("say or type it, check the card, save with one tap, undo", async ({ page, api }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Add what you spent today" })).toBeVisible();
    await expect(page.getByText("WhatsApp •••• 0071").first()).toBeAttached();
    await page.getByRole("button", { name: "Add an entry" }).click();
    const sheet = page.getByRole("dialog", { name: "Add money in or out" });
    await sheet.getByRole("button", { name: "Paid the milkman 500" }).click();
    await sheet.getByRole("button", { name: "Next" }).click();
    await expect(sheet.getByLabel("Amount (₹)")).toHaveValue("500");
    await expect(sheet.getByRole("radio", { name: "Money out" })).toBeChecked();
    await expect(sheet.getByLabel("Category")).toHaveValue("groceries");
    await sheet.getByRole("button", { name: "Save" }).click();
    await expect(sheet.getByText("Added: ₹500 · milkman")).toBeVisible();
    expect(api.transactions[0]?.source_modes).toEqual(["manual_entry"]);
    await sheet.getByRole("button", { name: "Undo" }).click();
    await expect(sheet.getByText("Undone: ₹500 · milkman")).toBeVisible();
    expect(api.transactions[0]?.status).toBe("needs_review");
    await sheet.getByRole("button", { name: "Done" }).click();
    await expect(sheet).toBeHidden();
  });

  test("a question goes to Ask instead of becoming a record", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    const sheet = page.getByRole("dialog", { name: "Add money in or out" });
    await sheet.getByLabel("What happened?").fill("How much did I spend this week?");
    await sheet.getByRole("button", { name: "Next" }).click();
    await expect(sheet.getByRole("link", { name: "Ask FinBoy instead" })).toBeVisible();
  });

  test("Gmail waits for Google's review; delete my account leaves FinBoy", async ({ page, api }) => {
    await page.goto("/sources");
    await expect(page.getByText("Gmail import is invite-only while Google reviews FinBoy.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Connect Gmail" })).toHaveCount(0);
    await page.goto("/privacy");
    await page.getByRole("button", { name: "Delete my account" }).click();
    await page.getByRole("button", { name: "Delete everything" }).click();
    await expect(page).toHaveURL(/\/$/);
    expect(api.requests.some((item) => item.path === "/api/v1/account/delete")).toBe(true);
    expect(api.signedIn).toBe(false);
  });
});
