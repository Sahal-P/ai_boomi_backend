import assert from "node:assert/strict";
import { test } from "node:test";
import type { SessionView } from "./api/auth.ts";
import { entryFor, entryWithNumber } from "./whatsapp-entry.ts";

type SignIn = SessionView["sign_in"];

function signedOut(overrides: Partial<SignIn> = {}) {
  return {
    authenticated: false,
    sign_in: {
      whatsapp: true,
      whatsapp_number: "919000000099",
      google_client_id: null,
      password: false,
      gmail: false,
      signup_open: true,
      ...overrides,
    },
  };
}

test("an authenticated household can open its dashboard even while WhatsApp sign-ups are open", () => {
  assert.deepEqual(entryFor({ ...signedOut(), authenticated: true }), { kind: "dashboard" });
});

test("open sign-ups start in FinBoy's WhatsApp chat with a greeting typed in", () => {
  assert.deepEqual(entryFor(signedOut()), { kind: "chat", href: "https://wa.me/919000000099?text=Hi%20FinBoy" });
});

test("closed sign-ups, WhatsApp off or no public number fall back to the sign-in page", () => {
  assert.deepEqual(entryFor(signedOut({ signup_open: false })), { kind: "web" });
  assert.deepEqual(entryFor(signedOut({ whatsapp: false })), { kind: "web" });
  assert.deepEqual(entryFor(signedOut({ whatsapp_number: null })), { kind: "web" });
});

test("an unreachable API falls back to the sign-in page", () => {
  assert.deepEqual(entryFor(null), { kind: "web" });
});

test("a page's greeting and ref ride in the chat link", () => {
  assert.deepEqual(entryFor(signedOut(), "നമസ്കാരം FinBoy (ref K7Q2MX)"), {
    kind: "chat",
    href: "https://wa.me/919000000099?text=%E0%B4%A8%E0%B4%AE%E0%B4%B8%E0%B5%8D%E0%B4%95%E0%B4%BE%E0%B4%B0%E0%B4%82%20FinBoy%20(ref%20K7Q2MX)",
  });
});

test("a page built with FinBoy's number opens the chat before and without the session check", () => {
  const chat = { kind: "chat", href: "https://wa.me/919000000088?text=Hi%20FinBoy" };
  assert.deepEqual(entryWithNumber(undefined, "919000000088"), chat);
  assert.deepEqual(entryWithNumber(null, "919000000088"), chat);
  assert.deepEqual(entryWithNumber(undefined, null), { kind: "loading" });
  assert.deepEqual(entryWithNumber(null, null), { kind: "web" });
  // Once the check answers, it decides: the dashboard, or the sign-in page while sign-ups are closed.
  assert.deepEqual(entryWithNumber({ ...signedOut(), authenticated: true }, "919000000088"), { kind: "dashboard" });
  assert.deepEqual(entryWithNumber(signedOut({ signup_open: false }), "919000000088"), { kind: "web" });
  assert.deepEqual(entryWithNumber(signedOut(), "919000000088"), { kind: "chat", href: "https://wa.me/919000000099?text=Hi%20FinBoy" });
});
