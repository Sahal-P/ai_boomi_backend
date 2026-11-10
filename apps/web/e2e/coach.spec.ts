import { expect, test } from "./support/fixtures.ts";

// Advisor phase 3: Home's "For you", from the same checks as the coach's WhatsApp nudges.
test.describe("with the coach on", () => {
  test.use({ scenario: { authRequired: false, advisor: true, coach: true, whatsapp: true } });

  test("Home shows what the coach found, where to look, and hands a question to Ask", async ({ page, api }) => {
    await page.goto("/dashboard");
    const card = page.getByRole("region", { name: "For you" });
    await expect(card.getByRole("listitem")).toHaveCount(3);
    await expect(card.getByRole("heading", { name: "Due soon" })).toBeVisible();
    await expect(card.getByText("Electricity bill: ₹1,500 due tomorrow.")).toBeVisible();
    await expect(card.getByRole("link", { name: "Open the record" })).toHaveAttribute("href", /^\/transactions\?selected=/);
    await expect(card.getByRole("link", { name: "Get one a day on WhatsApp" })).toHaveAttribute(
      "href",
      "https://wa.me/919000000099?text=coach%20on",
    );

    await card.getByRole("link", { name: "See bills" }).click();
    await expect(page).toHaveURL(/#obligations$/);

    await card.getByRole("link", { name: "Ask FinBoy: How can I spend less on food & dining?" }).click();
    await expect(page.getByLabel("Your question")).toHaveValue("How can I spend less on food & dining?");
    await expect(page).toHaveURL(/\/assistant$/);
    // Typed in, never sent by itself.
    expect(api.requests.filter((item) => item.path.startsWith("/api/v1/assistant/ask"))).toHaveLength(0);
  });

  test("a failed For you never blanks Home: the month and bills still show", async ({ page, api }) => {
    api.failNext(/\/api\/v1\/coach/, 503, "source_unavailable");
    await page.goto("/dashboard");
    await expect(page.getByRole("region", { name: /Left this month/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bills due" })).toBeVisible();
    await expect(page.getByRole("region", { name: "For you" })).toHaveCount(0);
    // No error notice for it in the page (Next's route announcer sits outside main).
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  });

  test("an earlier month shows no coach", async ({ page }) => {
    await page.goto("/dashboard?year=2026&month=9");
    await expect(page.getByRole("heading", { name: "Bills due" })).toBeVisible();
    await expect(page.getByRole("region", { name: "For you" })).toHaveCount(0);
  });
});

test.describe("with WhatsApp nudges already on", () => {
  test.use({ scenario: { authRequired: false, advisor: true, coach: true, whatsapp: true, coachWhatsApp: "on" } });

  test("Home says how to stop them", async ({ page }) => {
    await page.goto("/dashboard");
    const card = page.getByRole("region", { name: "For you" });
    await expect(card.getByText(/Send “coach off” there to stop/)).toBeVisible();
    await expect(card.getByRole("link", { name: "Get one a day on WhatsApp" })).toHaveCount(0);
  });
});

test.describe("with the coach off", () => {
  test.use({ scenario: { authRequired: false, advisor: true } });

  test("Home is unchanged and never asks for nudges", async ({ page, api }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Bills due" })).toBeVisible();
    await expect(page.getByRole("region", { name: "For you" })).toHaveCount(0);
    expect(api.requests.filter((item) => item.path === "/api/v1/coach")).toHaveLength(0);
  });
});
