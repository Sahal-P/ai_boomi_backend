import assert from "node:assert/strict";
import { test } from "node:test";
import type { SessionView } from "./api/auth.ts";
import { entryFor } from "./whatsapp-entry.ts";

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
