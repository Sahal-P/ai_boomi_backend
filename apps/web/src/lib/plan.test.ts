import assert from "node:assert/strict";
import { test } from "node:test";
import { type Plan, planSchema, startCheckout } from "./api/billing.ts";
import { sessionSchema } from "./api/auth.ts";
import { ApiError, requestJson } from "./api/http.ts";
import { payDate } from "./pay-copy.ts";
import { daysLeft, homeNotice, premiumUntil, rupees, shortDate, startsLine, statusLine } from "./plan.ts";
import { onPremiumRequired } from "./premium-events.ts";
import { z } from "zod";

const NOW = new Date("2026-11-25T10:00:00+05:30");

function plan(overrides: Partial<Plan> = {}): Plan {
  return planSchema.parse({
    state: "trial",
    premium: true,
    trial_ends_at: "2026-12-02T00:00:00+05:30",
    paid_through: null,
    renewal: null,
    next_charge_on: null,
    grace_until: null,
    price_minor: 29900,
    can_pay: true,
    autopay_available: false,
    checkout_origin: "https://test.payu.in",
    contact: { email: null, phone: "•••• 4821", phone_from_whatsapp: true },
    ...overrides,
  });
}

test("days left count calendar days in India, so the last day says 'ends today'", () => {
  assert.equal(daysLeft("2026-12-02T00:00:00+05:30", NOW), 7);
  assert.equal(daysLeft("2026-11-25T23:30:00+05:30", NOW), 0);
  // 20:00 UTC on 1 Dec is already 2 Dec in India.
  assert.equal(daysLeft("2026-12-01T20:00:00Z", NOW), 7);
  assert.equal(shortDate("2026-12-01T20:00:00Z"), "2 Dec");
  assert.equal(shortDate("2026-12-02"), "2 Dec");
  assert.equal(rupees(29900), "₹299");
});

test("the account menu names every plan state in a few words", () => {
  assert.equal(statusLine(plan(), NOW), "Trial · 7 days left");
  assert.equal(statusLine(plan({ trial_ends_at: "2026-11-26T09:00:00+05:30" }), NOW), "Trial · 1 day left");
  assert.equal(statusLine(plan({ trial_ends_at: "2026-11-25T18:00:00+05:30" }), NOW), "Trial · ends today");
  assert.equal(statusLine(plan({ state: "included" }), NOW), "Premium included");
  assert.equal(statusLine(plan({ state: "free", premium: false }), NOW), "Free plan");
  assert.equal(statusLine(plan({ state: "grace" }), NOW), "Payment didn't go through");
  assert.equal(
    statusLine(plan({ state: "active", paid_through: "2027-01-02T00:00:00+05:30", renewal: "autopay" }), NOW),
    "Premium · AutoPay on",
  );
  assert.equal(
    statusLine(plan({ state: "trial", paid_through: "2027-01-02T00:00:00+05:30", renewal: "manual" }), NOW),
    "Premium until 2 Jan",
    "paid during the trial: the paid month follows it",
  );
});

test("Home stays quiet until the last week, then offers to keep Premium", () => {
  assert.equal(homeNotice(null, NOW), null, "billing off");
  assert.equal(homeNotice(plan({ state: "included" }), NOW), null);
  assert.equal(homeNotice(plan({ trial_ends_at: "2026-12-03T00:00:00+05:30" }), NOW), null, "8 days left");
  assert.deepEqual(homeNotice(plan(), NOW), {
    tone: "calm",
    text: "Premium trial · 7 days left",
    action: "Keep Premium",
  });
  const paid = { state: "active", trial_ends_at: "2026-10-28T00:00:00+05:30", paid_through: "2026-11-28T00:00:00+05:30" } as const;
  assert.deepEqual(homeNotice(plan({ ...paid, renewal: "manual" }), NOW), {
    tone: "calm",
    text: "Premium · 3 days left",
    action: "Keep Premium",
  });
  assert.equal(homeNotice(plan({ ...paid, renewal: "autopay" }), NOW), null, "AutoPay renews by itself");
  assert.equal(homeNotice(plan({ state: "grace" }), NOW)?.tone, "attention");
  assert.equal(homeNotice(plan({ state: "free", premium: false }), NOW)?.action, "Get Premium");
});

test("money paid during the trial starts counting when the trial ends", () => {
  assert.equal(premiumUntil(plan({ paid_through: "2027-01-02T00:00:00+05:30" })), "2027-01-02T00:00:00+05:30");
  assert.equal(
    startsLine(plan(), NOW),
    "Your free trial continues until 2 Dec; your first paid month starts then.",
  );
  assert.equal(
    startsLine(plan({ state: "active", paid_through: "2026-12-20T00:00:00+05:30" }), NOW),
    "Your next month starts on 20 Dec, when this one ends.",
  );
  assert.equal(startsLine(plan({ state: "free", trial_ends_at: "2026-11-01T00:00:00+05:30" }), NOW), null);
  assert.equal(payDate("2026-12-02T00:00:00+05:30", "en"), "2 Dec");
  assert.notEqual(payDate("2026-12-02T00:00:00+05:30", "hi"), "2 Dec", "Hindi months are written in Hindi");
});

test("older sessions without a plan still parse, as billing off", () => {
  const session = sessionSchema.parse({
    required: true,
    authenticated: true,
    household: { owner: false, joined_via: "whatsapp", whatsapp: "•••• 0071", google: null },
    sign_in: {
      whatsapp: true,
      whatsapp_number: "919000000099",
      google_client_id: null,
      password: false,
      signup_open: true,
      gmail: false,
    },
  });
  assert.equal(session.plan, null);
  assert.equal(sessionSchema.parse({ ...session, plan: plan() }).plan?.state, "trial");
});

test("a checkout is posted only to PayU's own checkout addresses", async (t) => {
  const reply = (action: string) =>
    Response.json({ payment_id: "6f1f3c1e-8a59-4d55-9a4e-3f5d2a1b0c9d", action, fields: { key: "k", hash: "h" } });
  t.mock.method(globalThis, "fetch", async () => reply("https://secure.payu.in/_payment"));
  assert.equal((await startCheckout({ email: " a@b.in " })).action, "https://secure.payu.in/_payment");
  t.mock.method(globalThis, "fetch", async () => reply("https://payu.example.com/_payment"));
  await assert.rejects(startCheckout({}), (error: unknown) => error instanceof ApiError);
});

test("a Premium answer opens the upgrade sheet wherever the person was", async (t) => {
  let opened = 0;
  const stop = onPremiumRequired(() => {
    opened += 1;
  });
  t.after(stop);
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ error: { code: "premium_required", message: "This is part of FinBoy Premium." } }, { status: 402 }),
  );
  await assert.rejects(requestJson("/api/v1/assistant/ask", z.object({})), (error: unknown) =>
    error instanceof ApiError && error.kind === "premium" && error.code === "premium_required");
  assert.equal(opened, 1);
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ error: { code: "already_paid", message: "Already paid." } }, { status: 409 }),
  );
  await assert.rejects(requestJson("/api/v1/billing/checkout", z.object({})));
  assert.equal(opened, 1, "other refusals don't open it");
});
