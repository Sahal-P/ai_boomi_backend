import { ids, PASSWORD } from "./support/fake-api.ts";
import { expect, signIn, test } from "./support/fixtures.ts";

test.use({ scenario: { authRequired: true, signedIn: false } });

test("a signed-out import link returns to that import after sign-in, via the same-origin proxy", async ({ page, api, foreignApiCalls }) => {
  await signIn(page, `/import/${ids.partialImport}`);
  await expect(page).toHaveURL(new RegExp(`/import/${ids.partialImport}$`));
  await expect(page.getByRole("heading", { name: "4 records need review · 2 emails couldn't be read" })).toBeVisible();
  await expect(page).toHaveTitle("Import results · FinBoy");
  expect(foreignApiCalls).toEqual([]);
  expect(api.requests.some((item) => item.path === "/api/v1/auth/login")).toBe(true);
});

test("sign-in explains a wrong password without leaving the page", async ({ page, api }) => {
  await page.goto("/review");
  await expect(page.getByText("Sign in or create your account — you'll go straight on to Review.")).toBeVisible();
  await page.getByLabel("Household password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "That password didn't work" })).toBeVisible();
  await expect(page.getByLabel("Household password")).toHaveAttribute("aria-invalid", "true");
  expect(api.signedIn).toBe(false);
});

test("unsafe return destinations fall back to the overview", async ({ page }) => {
  await page.goto("/login?next=https%3A%2F%2Fevil.example%2Fdashboard");
  await page.getByLabel("Household password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("an expired session during a correction keeps the draft and re-signs in place", async ({ page, api }) => {
  await signIn(page, `/transactions?scope=all&selected=${ids.merchantUnclear}`);
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Unknown merchant" })).toBeVisible();
  await dialog.getByLabel("Merchant or payer").fill("Sample Corner Shop");
  api.signedIn = false;
  await dialog.getByRole("button", { name: "Save and confirm" }).click();
  const reauth = page.getByRole("dialog", { name: "Sign in to continue" });
  await expect(reauth).toBeVisible();
  await expect(reauth).toContainText("unsaved edits stay as they are");
  await reauth.getByLabel("Household password").fill(PASSWORD);
  await reauth.getByRole("button", { name: "Sign in" }).click();
  await expect(reauth).toBeHidden();
  await expect(dialog.getByLabel("Merchant or payer")).toHaveValue("Sample Corner Shop");
  await dialog.getByRole("button", { name: "Save and confirm" }).click();
  await expect(dialog.getByText("Confirmed. It now counts toward your totals.")).toBeVisible();
  const decision = api.requests.filter((item) => item.path.endsWith("/decisions")).at(-1);
  expect(decision?.body).toMatchObject({ action: "confirm", correction: { merchant: "Sample Corner Shop" } });
});

test("sign-out lives in account navigation, never floating over content", async ({ page }, testInfo) => {
  await signIn(page, "/sources");
  if (testInfo.project.name === "desktop") {
    await expect(page.getByRole("complementary").getByRole("button", { name: "Sign out" })).toBeVisible();
  } else {
    await page.getByRole("button", { name: "Account and settings" }).click();
    await expect(page.getByRole("menuitem", { name: "Sign out" })).toBeVisible();
    await page.keyboard.press("Escape");
  }
  await expect(page.locator("button", { hasText: "Sign out" }).filter({ visible: true })).toHaveCount(testInfo.project.name === "desktop" ? 1 : 0);
});
