import { expect, test } from "./support/fixtures.ts";

// Advisor round: Ask for every household (here on the Free plan), kept chats and Memory.
test.use({ scenario: { authRequired: false, advisor: true, plan: "free" } });

test("a Free household asks by typing, follows up in the same chat and reopens it", async ({ page, api }) => {
  await page.goto("/assistant");
  await expect(page.getByRole("button", { name: "Who do I pay the most?" })).toBeVisible();
  await page.getByLabel("Your question").fill("How much did I spend on food this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const first = page.getByRole("article", { name: /food this month/ });
  await expect(first.getByText("You spent ₹4,200 on food and dining this month")).toBeVisible();
  await first.getByRole("button", { name: "And last month?" }).click();
  const second = page.getByRole("article", { name: /And last month/ });
  await expect(second.getByText("Last month you spent ₹3,000")).toBeVisible();
  const asks = api.requests.filter((item) => item.method === "POST" && item.path === "/api/v1/assistant/ask/stream");
  const threads = asks.map((item) => (item.body as { thread_id?: string }).thread_id ?? null);
  expect(threads[0]).toBeNull();
  expect(threads[1]).toBe(api.chats[0]?.id);

  await page.reload();
  await page.getByRole("button", { name: "Recent chats" }).click();
  await page.getByRole("button", { name: /How much did I spend on food this month/ }).click();
  await expect(page.getByRole("article", { name: /And last month/ }).getByText("Last month you spent ₹3,000")).toBeVisible();
  await expect(page.getByRole("article", { name: /And last month/ }).getByRole("button", { name: "Play answer" })).toHaveCount(0);
});

test("what FinBoy remembers shows on the answer and can be edited, switched off and forgotten", async ({ page, api }) => {
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("Please remember I'm saving ₹40,000 for a bike");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByRole("article", { name: /remember/ });
  await expect(answer.getByRole("listitem").filter({ hasText: "Saved to memory:" })).toContainText(
    "Saving ₹40,000 for a bike",
  );
  await answer.getByRole("link", { name: "Manage" }).click();

  await expect(page).toHaveTitle(/Memory/);
  await expect(page.getByRole("heading", { name: "Goals" })).toBeVisible();
  await page.getByRole("button", { name: "Edit: Saving ₹40,000 for a bike" }).click();
  await page.getByLabel("Memory").fill("My PIN is 1234");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "That memory couldn't be changed" })).toBeVisible();
  await page.getByLabel("Memory").fill("Saving ₹40,000 for a bike by March");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "Saving ₹40,000 for a bike by March" })).toBeVisible();

  await page.getByRole("switch", { name: "Let FinBoy remember" }).click();
  await expect(page.getByRole("status").getByText("Memory is off.")).toBeVisible();
  expect(api.memoryEnabled).toBe(false);

  await page.getByRole("button", { name: "Forget everything" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Forget everything" }).click();
  await expect(page.getByText("Nothing saved yet.")).toBeVisible();
  expect(api.memories).toHaveLength(0);
});

test("an answer from FinBoy's guides links each guide's official site", async ({ page, api }) => {
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("When does the PM-KISAN money come?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByRole("article", { name: /PM-KISAN money/ });
  await expect(answer.getByText("PM-KISAN pays eligible farmer families ₹6,000 a year")).toBeVisible();
  await expect(answer.getByText("Official sites")).toBeVisible();
  const guide = answer.getByRole("link", { name: /PM-KISAN.*official site, opens in a new tab/ });
  await expect(guide).toHaveAttribute("href", "https://pmkisan.gov.in");
  await expect(guide).toHaveAttribute("target", "_blank");
  await expect(guide).toHaveAttribute("rel", "noopener noreferrer");
  expect(api.requests.some((item) => item.path === "/api/v1/assistant/ask")).toBe(false);
});

test("a failure inside the stream explains itself and can be asked again", async ({ page }) => {
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("Is the advisor unavailable?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByRole("article", { name: /unavailable/ });
  await expect(answer.getByRole("button", { name: "Ask again" })).toBeVisible();
});

test("the account menu opens Memory", async ({ page }, testInfo) => {
  await page.goto("/assistant");
  const account = testInfo.project.name === "desktop"
    ? page.getByRole("button", { name: /Your household/ })
    : page.getByRole("button", { name: "Account and settings" });
  await account.click();
  await page.getByRole("menuitem", { name: "Memory" }).click();
  await expect(page.getByRole("heading", { name: "Memory", level: 1 })).toBeVisible();
});
