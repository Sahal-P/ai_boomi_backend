import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { chatLink, safeReturnPath, sessionSchema, startGoogle, startWhatsApp } from "./auth.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("sign-in returns only to same-origin app paths", () => {
  assert.equal(safeReturnPath("/import/30000000-0000-4000-8000-000000000001"), "/import/30000000-0000-4000-8000-000000000001");
  assert.equal(safeReturnPath("/transactions?selected=abc&q=food"), "/transactions?selected=abc&q=food");
  assert.equal(safeReturnPath("/sources?intent=gmail"), "/sources?intent=gmail");
  for (const unsafe of [
    null,
    "",
    "https://evil.example/dashboard",
    "//evil.example/dashboard",
    "/\\evil.example",
    "javascript:alert(1)",
    "/login",
    "/api/v1/money/summary",
    "/dashboard/../api/v1/auth/logout",
    `/review?${"x".repeat(600)}`,
  ]) {
    assert.equal(safeReturnPath(unsafe), "/dashboard", String(unsafe));
  }
});

const signIn = {
  whatsapp: true,
  whatsapp_number: "919000000099",
  google_client_id: "123456-abcdefgh.apps.googleusercontent.com",
  password: false,
  signup_open: true,
  gmail: false,
};

test("the session carries only masked sign-in details and public configuration", () => {
  const view = sessionSchema.parse({
    authenticated: true,
    required: true,
    household: { owner: false, joined_via: "whatsapp", whatsapp: "•••• 0071", google: null },
    sign_in: signIn,
  });
  assert.equal(view.household?.whatsapp, "•••• 0071");
  for (const bad of [
    { ...signIn, whatsapp_number: "+91 90000" },
    { ...signIn, google_client_id: "client-secret-looking-value" },
  ]) {
    assert.equal(
      sessionSchema.safeParse({ authenticated: false, required: true, household: null, sign_in: bad }).success,
      false,
    );
  }
});

test("a WhatsApp start accepts only a wa.me link carrying its code", async () => {
  const reply = (body: unknown) => {
    globalThis.fetch = async () => new Response(JSON.stringify(body), { status: 200 });
  };
  const good = {
    code: "K7Q2-9FXM",
    link: "https://wa.me/919000000099?text=FinBoy%20login%20code%20K7Q2-9FXM",
    expires_at: "2026-10-27T10:00:00Z",
  };
  reply(good);
  assert.deepEqual(await startWhatsApp(), good);
  for (const link of ["javascript:alert(1)", "https://evil.example/?text=x", "https://wa.me/12?text=<b>"]) {
    reply({ ...good, link });
    await assert.rejects(startWhatsApp(), { kind: "invalid_response" });
  }
});

test("the WhatsApp-only link opens FinBoy's chat with a greeting typed in", () => {
  assert.equal(chatLink("919000000099"), "https://wa.me/919000000099?text=Hi%20FinBoy");
  assert.equal(
    chatLink("919000000099", "नमस्ते FinBoy"),
    "https://wa.me/919000000099?text=%E0%A4%A8%E0%A4%AE%E0%A4%B8%E0%A5%8D%E0%A4%A4%E0%A5%87%20FinBoy",
  );
});

test("Google and WhatsApp starting together keep the same browser nonce", async () => {
  let cookie: string | undefined;
  let releaseFirst!: () => void;
  const firstResponse = new Promise<void>((resolve) => { releaseFirst = resolve; });
  globalThis.fetch = async (input) => {
    const path = String(input);
    const nonce = cookie ?? (path.endsWith("/google/start") ? "b" : "a").repeat(64);
    if (path.endsWith("/whatsapp/start")) await firstResponse;
    // Model Set-Cookie delivery: each fresh request initially has no login cookie.
    cookie = nonce;
    return new Response(JSON.stringify(path.endsWith("/google/start") ? { nonce } : {
      code: "K7Q2-9FXM",
      link: "https://wa.me/919000000099?text=FinBoy%20login%20code%20K7Q2-9FXM",
      expires_at: "2026-10-28T10:00:00Z",
    }));
  };
  const whatsapp = startWhatsApp();
  const google = startGoogle();
  await new Promise<void>((resolve) => setImmediate(resolve));
  releaseFirst();
  await whatsapp;
  assert.equal((await google).nonce, cookie);
});

test("a failed provider start does not block the other sign-in option", async () => {
  globalThis.fetch = async (input) => String(input).endsWith("/whatsapp/start")
    ? new Response("", { status: 503 })
    : new Response(JSON.stringify({ nonce: "c".repeat(64) }));
  const whatsapp = assert.rejects(startWhatsApp(), { status: 503 });
  const google = startGoogle();
  await whatsapp;
  assert.equal((await google).nonce, "c".repeat(64));
});
