import assert from "node:assert/strict";
import { test } from "node:test";
import type { SessionView } from "./api/auth.ts";
import { entryFor } from "./whatsapp-entry.ts";

type SignIn = SessionView["sign_in"];

function signIn(overrides: Partial<SignIn> = {}): SignIn {
  return {
    whatsapp: true,
    whatsapp_number: "919000000099",
    google_client_id: null,
    password: false,
    gmail: false,
    signup_open: true,
    ...overrides,
  };
}

test("open sign-ups start in FinBoy's WhatsApp chat with a greeting typed in", () => {
  assert.deepEqual(entryFor(signIn()), { kind: "chat", href: "https://wa.me/919000000099?text=Hi%20FinBoy" });
});

test("closed sign-ups, WhatsApp off or no public number fall back to the sign-in page", () => {
  assert.deepEqual(entryFor(signIn({ signup_open: false })), { kind: "web" });
  assert.deepEqual(entryFor(signIn({ whatsapp: false })), { kind: "web" });
  assert.deepEqual(entryFor(signIn({ whatsapp_number: null })), { kind: "web" });
});

test("an unreachable API falls back to the sign-in page", () => {
  assert.deepEqual(entryFor(null), { kind: "web" });
});
