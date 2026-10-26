import { expect, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: false } });

test("each answer is paired with its question, style and period; a failed follow-up keeps it", async ({ page }) => {
  await page.goto("/assistant");
  await expect(page).toHaveTitle("Ask FinBoy · FinBoy");
  await page.getByLabel("Your question").fill("How much did I spend at Sample Books this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByLabel("Your question")).toHaveValue("");
  const first = page.getByRole("article", { name: /Sample Books this month/ });
  await expect(first.getByText("October 2026")).toBeVisible();
  await expect(first.getByText("You asked · reply style Match my question")).toBeVisible();
  await page.getByLabel("Your question").fill("Is the service unavailable?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const failed = page.getByRole("article", { name: /service unavailable/ });
  await expect(failed.getByRole("alert")).toContainText("FinBoy couldn't answer that");
  await expect(first.getByText("Spent at Sample Books")).toBeVisible();
});

test("a slow question can be cancelled without losing earlier answers", async ({ page, api }) => {
  api.delay(/assistant\/ask/, 4_000);
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("How much did I spend this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const pending = page.getByRole("article", { name: /spend this month/ });
  await expect(pending.getByText("Thinking through your question…")).toBeVisible();
  await pending.getByRole("button", { name: "Cancel" }).click();
  await expect(pending.getByText("You cancelled this question. Nothing was saved.")).toBeVisible();
});

test("romanized replies are announced as romanized, with localized labels and warnings", async ({ page }) => {
  await page.goto("/assistant");
  await page.getByLabel("Reply style").selectOption("hinglish");
  await page.getByLabel("Your question").fill("Sample Books par kitna kharch hua?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByRole("article", { name: /Sample Books par/ });
  await expect(answer.locator('[lang="hi-Latn"]').first()).toBeVisible();
  await expect(answer.getByText("Sample Books par kharch").first()).toBeVisible();
  await expect(answer.getByText("Kuch records review baaki hain")).toBeVisible();
  await expect(answer.getByRole("heading", { name: /Sambandhit records/ })).toBeVisible();
  await expect(answer.getByRole("button", { name: "Jawab sunein" })).toBeVisible();
  await expect(answer.getByText(/Pending Review|Incomplete Coverage/)).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("Reply style")).toHaveValue("hinglish");
});

test("playing an answer prepares audio on the tap and keeps the text on failure", async ({ page, api }) => {
  await page.goto("/assistant");
  await page.getByLabel("Your question").fill("How much did I spend at Sample Books this month?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.getByRole("article", { name: /Sample Books this month/ });
  await answer.getByRole("button", { name: "Play answer" }).click();
  await expect(answer.getByRole("button", { name: /Stop audio|Audio ready — play|Play answer/ })).toBeVisible();
  api.failNext(/assistant\/speak/, 503, "provider_unavailable");
  await page.getByLabel("Your question").fill("How much did I spend at Sample Books today?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const second = page.getByRole("article", { name: /Sample Books today/ });
  await second.getByRole("button", { name: "Play answer" }).click();
  await expect(second.getByRole("alert")).toContainText("Audio isn't available for this answer");
  await expect(second.getByText("Spent at Sample Books")).toBeVisible();
  await expect(second.getByRole("button", { name: "Try audio again" })).toBeVisible();
});

test("a denied microphone explains how to recover; nothing records without a tap", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: () => Promise.reject(new DOMException("denied", "NotAllowedError")) },
    });
  });
  await page.goto("/assistant");
  await expect(page.getByText(/Recording ·/)).toHaveCount(0);
  await page.getByRole("button", { name: "Record a question" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Microphone access is blocked" })).toBeVisible();
  await expect(page.getByLabel("Your question")).toBeEnabled();
});

test("a recording is transcribed for review and never sent automatically", async ({ page, api }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "fake-device capture is exercised once");
  await page.addInitScript(() => {
    // Synthetic microphone: an oscillator stream stands in for a real device.
    const getUserMedia = async () => {
      const context = new AudioContext();
      const oscillator = context.createOscillator();
      const destination = context.createMediaStreamDestination();
      oscillator.connect(destination);
      oscillator.start();
      await context.resume();
      return destination.stream;
    };
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  });
  await page.goto("/assistant");
  await page.getByRole("button", { name: "Record a question" }).click();
  await expect(page.getByText(/Recording · 0:0\d/)).toBeVisible();
  await expect(page.getByText(/left\)/)).toBeVisible();
  // An immediate stop can legitimately capture no frames; wait for actual recording time.
  await expect(page.getByText(/Recording · 0:0[1-9]/)).toBeVisible();
  await page.getByRole("button", { name: "Stop and transcribe" }).click();
  await expect(page.getByLabel(/Your question/)).toHaveValue("How much did I spend on food this month?");
  await expect(page.getByText("nothing is sent until you do")).toBeVisible();
  expect(api.requests.some((item) => item.path === "/api/v1/assistant/ask")).toBe(false);
  await page.getByRole("button", { name: "Discard transcript" }).click();
  await expect(page.getByLabel("Your question")).toHaveValue("");
});
