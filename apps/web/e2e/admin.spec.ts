import { ADMIN_EMAIL, ADMIN_PASSWORD, adminIds, TEMPORARY_PASSWORD } from "./support/fake-admin-api.ts";
import { expect, test } from "./support/fixtures.ts";

/**
 * The admin panel (docs/admin-round/contract.md) against the TEST-ONLY admin double: sign-in,
 * the temporary-password detour, every page, each household action's confirmation, and the
 * headers that keep /admin out of frames, caches and search engines.
 */

test.describe("signed out", () => {
  test.use({ scenario: { admin: { signedIn: false } } });

  test("an admin page sends the browser to sign in, then back to it", async ({ page }) => {
    await page.goto("/admin/households?q=a1b2");
    await expect(page).toHaveURL(/\/admin\/login\?next=%2Fadmin%2Fhouseholds%3Fq%3Da1b2$/);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in to the admin panel" })).toBeVisible();
    await page.getByLabel("Email").fill(ADMIN_EMAIL);
    await page.getByLabel("Password").fill("not-the-synthetic-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    // Scoped: Next's route announcer is an alert too.
    const form = page.getByRole("region", { name: "Sign in to the admin panel" });
    await expect(form.getByRole("alert")).toContainText("That email and password didn't work");
    // The typed password is never kept after a submit.
    await expect(page.getByLabel("Password")).toHaveValue("");
    await page.getByLabel("Password").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/admin\/households\?q=a1b2$/);
    await expect(page.getByRole("heading", { level: 1, name: "Households" })).toBeVisible();
  });

  test("sign-in never returns to a page outside the admin panel", async ({ page }) => {
    await page.goto("/admin/login?next=%2F%2Fevil.example%2Fadmin");
    await page.getByLabel("Email").fill(ADMIN_EMAIL);
    await page.getByLabel("Password").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/admin$/);
  });
});

test.describe("temporary password", () => {
  test.use({ scenario: { admin: { signedIn: false, mustChange: true } } });

  test("a new admin chooses their own password before anything else opens", async ({ page }) => {
    await page.goto("/admin/login");
    await page.getByLabel("Email").fill(ADMIN_EMAIL);
    await page.getByLabel("Password").fill(TEMPORARY_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/admin\/password$/);
    await expect(page.getByRole("heading", { level: 1, name: "Choose your own password" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin navigation" })).toHaveCount(0);
    await page.goto("/admin/households");
    await expect(page).toHaveURL(/\/admin\/password$/);
    await page.getByLabel("Temporary password").fill(TEMPORARY_PASSWORD);
    await page.getByLabel("New password", { exact: true }).fill("too-short");
    await page.getByLabel("Repeat the new password").fill("too-short");
    await expect(page.getByRole("button", { name: "Save new password" })).toBeDisabled();
    await page.getByLabel("New password", { exact: true }).fill("a-new-synthetic-password");
    await page.getByLabel("Repeat the new password").fill("a-new-synthetic-password");
    await page.getByRole("button", { name: "Save new password" }).click();
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  });
});

test("the overview shows counts, never a household's records", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
  await expect(page.getByText("Self-serve households")).toBeVisible();
  await expect(page.getByText("₹299", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Households by kind" })).toContainText("Village pilot");
  await expect(page.getByRole("region", { name: "Sign-ups" })).toContainText("84");
});

test("find a household by its exact number, then suspend and restore it", async ({ page }) => {
  await page.goto("/admin/households");
  const rows = page.getByRole("list", { name: "Households" }).getByRole("link");
  await expect(rows).toHaveCount(5);
  await page.getByLabel("Household ID or phone number").fill("+91 98123 45670");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("a1b2c3d4");
  await rows.first().click();
  await expect(page.getByRole("heading", { name: "a1b2c3d4" })).toBeVisible();
  await page.getByRole("button", { name: "Suspend", exact: true }).click();
  const suspend = page.getByRole("alertdialog", { name: "Suspend this household?" });
  const confirm = suspend.getByRole("button", { name: "Suspend", exact: true });
  await expect(confirm).toBeDisabled();
  await suspend.getByLabel("Type a1b2c3d4 to confirm").fill("a1b2c3d4");
  await confirm.click();
  await expect(suspend).toBeHidden();
  await expect(page.getByText("Household suspended.")).toBeVisible();
  await page.getByRole("button", { name: "Restore", exact: true }).click();
  await page.getByRole("alertdialog", { name: "Restore this household?" }).getByRole("button", { name: "Restore" }).click();
  await expect(page.getByText("Household restored.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Suspend", exact: true })).toBeVisible();
});

test("an unknown number or a name finds nothing, and filters narrow the list", async ({ page }) => {
  await page.goto("/admin/households?q=9812345679");
  await expect(page.getByRole("heading", { name: "No household matches that search" })).toBeVisible();
  await page.goto("/admin/households?kind=pilot");
  const rows = page.getByRole("list", { name: "Households" }).getByRole("link");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("c3d4e5f6");
  await page.getByRole("button", { name: /^Filters/ }).click();
  await page.getByLabel("Kind").selectOption("");
  await page.getByLabel("Status").selectOption("suspended");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("d4e5f6a7");
});

test("erasing a pending sign-up needs its short ID typed back", async ({ page }) => {
  await page.goto(`/admin/households?selected=${adminIds.pending}`);
  await expect(page.getByRole("heading", { name: "b2c3d4e5" })).toBeVisible();
  await page.getByRole("button", { name: "Erase", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Erase this household?" });
  await expect(dialog).toContainText("never agreed");
  await dialog.getByLabel(/to confirm$/).fill("b2c3d4e4");
  await expect(dialog.getByRole("button", { name: "Erase", exact: true })).toBeDisabled();
  await dialog.getByLabel(/to confirm$/).fill("B2C3D4E5");
  await dialog.getByRole("button", { name: "Erase", exact: true }).click();
  await expect(page.getByText("Household erased.")).toBeVisible();
  await expect(page).not.toHaveURL(/selected=/);
  await expect(page.getByRole("list", { name: "Households" }).getByRole("link")).toHaveCount(4);
});

test("the owner's household can only be viewed", async ({ page }) => {
  await page.goto(`/admin/households?selected=${adminIds.owner}`);
  await expect(page.getByRole("heading", { name: "00000000" })).toBeVisible();
  await expect(page.getByText("The owner's household can only be viewed here.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Erase", exact: true })).toHaveCount(0);
});

test("give Premium days, create a pay link shown once, turn AutoPay off", async ({ page }) => {
  await page.goto(`/admin/households?selected=${adminIds.family}`);
  await page.getByRole("button", { name: "Give Premium days" }).click();
  const premium = page.getByRole("alertdialog", { name: "Give Premium days" });
  await premium.getByLabel("Days of Premium").fill("400");
  await expect(premium.getByRole("button", { name: "Give days" })).toBeDisabled();
  await premium.getByLabel("Days of Premium").fill("30");
  await premium.getByRole("button", { name: "Give days" }).click();
  await expect(page.getByText("Premium days given.")).toBeVisible();

  await page.getByRole("button", { name: "Create pay link" }).click();
  await page.getByRole("alertdialog", { name: "Create a pay link?" }).getByRole("button", { name: "Create link" }).click();
  const shown = page.getByRole("alertdialog", { name: "Pay link, shown once" });
  await expect(shown.getByLabel("Pay link")).toHaveValue("http://127.0.0.1:3032/pay#synthetic-pay-link");
  await shown.getByRole("button", { name: "Done" }).click();
  await expect(shown).toBeHidden();

  await page.getByRole("button", { name: "Turn off AutoPay" }).click();
  await page.getByRole("alertdialog", { name: "Turn off AutoPay?" }).getByRole("button", { name: "Turn off AutoPay" }).click();
  await expect(page.getByText("AutoPay turned off.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Turn off AutoPay" })).toHaveCount(0);
});

test("re-check a payment FinBoy hasn't heard back about", async ({ page }) => {
  await page.goto("/admin/payments");
  await expect(page.getByRole("heading", { level: 1, name: "Payments" })).toBeVisible();
  await expect(page.getByText("FBSYNTH0001", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Re-check with PayU" }).click();
  await expect(page.getByText("PayU says FBSYNTH0001 is paid.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Re-check with PayU" })).toHaveCount(0);
});

test("tidy stale sign-ups, and read the system settings", async ({ page }) => {
  await page.goto("/admin/signups");
  await page.getByRole("button", { name: "Tidy 2 sign-ups" }).click();
  await page.getByRole("alertdialog", { name: "Tidy sign-ups?" }).getByRole("button", { name: "Tidy now" }).click();
  await expect(page.getByText("Tidied: 2 sign-ups removed.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Nothing to tidy" })).toBeDisabled();
  await page.goto("/admin/system");
  await expect(page.getByRole("region", { name: "Switches" })).toContainText("SIGNUP_ENABLED");
  await expect(page.getByRole("region", { name: "Providers" })).toContainText("Missing");
  await expect(page.getByRole("region", { name: "Service" })).toContainText("0014_admin");
});

test("add an admin, disable another and sign out your other browsers", async ({ page }) => {
  await page.goto("/admin/admins");
  await page.getByLabel("Their email").fill("new.admin@example.test");
  await page.getByRole("button", { name: "Add admin" }).click();
  await expect(page.getByText(TEMPORARY_PASSWORD, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Hide it" }).click();
  await expect(page.getByText(TEMPORARY_PASSWORD, { exact: true })).toHaveCount(0);
  const colleague = page.getByRole("list", { name: "Admin accounts" }).getByRole("listitem").filter({ hasText: "colleague@example.test" });
  await colleague.getByRole("button", { name: "Disable" }).click();
  await page.getByRole("alertdialog", { name: "Disable this admin?" }).getByRole("button", { name: "Disable" }).click();
  await expect(colleague).toContainText("Disabled");
  await page.getByRole("button", { name: "Sign out the others" }).click();
  await page
    .getByRole("alertdialog", { name: "Sign out your other browsers?" })
    .getByRole("button", { name: "Sign out the others" })
    .click();
  await expect(page.getByRole("list", { name: "Your signed-in browsers" }).getByRole("listitem")).toHaveCount(1);
});

test("the audit log records actions, and signing out ends the session", async ({ page }) => {
  await page.goto(`/admin/households?selected=${adminIds.family}`);
  await page.getByRole("button", { name: "Sign out everywhere" }).click();
  await page
    .getByRole("alertdialog", { name: "Sign this household out everywhere?" })
    .getByRole("button", { name: "Sign out everywhere" })
    .click();
  await expect(page.getByText("Signed out everywhere.")).toBeVisible();
  await page.goto("/admin/audit");
  const first = page.getByRole("list", { name: "Audit entries" }).getByRole("listitem").first();
  await expect(first).toContainText("Signed a household out everywhere");
  await expect(first).toContainText("a1b2c3d4");
  await page.getByRole("button", { name: /^Admin account/ }).first().click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/admin\/login$/);
});

test("phones reach the other pages through the tab bar's More menu", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "desktop", "the sidebar lists every page on desktop");
  await page.goto("/admin");
  await page.getByRole("button", { name: "More pages" }).click();
  await page.getByRole("menuitem", { name: "Audit log" }).click();
  await expect(page).toHaveURL(/\/admin\/audit$/);
  await expect(page.getByRole("button", { name: "More pages, showing Audit log" })).toBeVisible();
});

test("a lost admin session sends the browser to sign in", async ({ page, api }) => {
  await page.goto("/admin/payments");
  await expect(page.getByText("FBSYNTH0001", { exact: true })).toBeVisible();
  api.admin.signedIn = false;
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page).toHaveURL(/\/admin\/login\?next=%2Fadmin%2Fpayments$/);
});

test("every admin page has a task title, one heading and no sideways scroll", async ({ page }) => {
  for (const [path, title] of [
    ["/admin", "Overview · FinBoy admin"],
    ["/admin/households", "Households · FinBoy admin"],
    ["/admin/payments", "Payments · FinBoy admin"],
    ["/admin/signups", "Sign-ups · FinBoy admin"],
    ["/admin/system", "System · FinBoy admin"],
    ["/admin/admins", "Admins · FinBoy admin"],
    ["/admin/audit", "Audit log · FinBoy admin"],
    ["/admin/password", "Password · FinBoy admin"],
    ["/admin/login", "Sign in · FinBoy admin"],
  ] as const) {
    await page.goto(path);
    await expect(page).toHaveTitle(title);
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
    await page.waitForLoadState("networkidle");
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
    expect(fits, `${path} is wider than the screen`).toBe(true);
  }
});

test("admin pages are never framed, cached or indexed", async ({ request }) => {
  for (const path of ["/admin", "/admin/login", "/admin/households"]) {
    const response = await request.get(path);
    expect(response.headers()["x-frame-options"], path).toBe("DENY");
    expect(response.headers()["cache-control"], path).toContain("no-store");
    expect(response.headers()["x-robots-tag"], path).toBe("noindex, nofollow");
    expect(await response.text(), path).toMatch(/<meta name="robots" content="noindex, nofollow/);
  }
  expect(await (await request.get("/robots.txt")).text()).toContain("Disallow: /admin");
  expect(await (await request.get("/sitemap.xml")).text()).not.toContain("/admin");
});
