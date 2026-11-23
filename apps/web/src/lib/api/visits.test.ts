import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { greeting, newRef, readUtm, recordVisit, REF_PATTERN, tapVisit } from "./visits.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

// The link Instagram gives a bio-link click (shared by the owner on 23 Nov 2026; click ID shortened).
const BIO_LINK = "?utm_source=ig&utm_medium=social&utm_content=link_in_bio&fbclid=PAdGRleAVwrqZleHRuA2FlbQIxMQBwZG9m";

test("Instagram's own bio-link tags are kept and its click ID is only noted", () => {
  const utm = readUtm(BIO_LINK);
  assert.deepEqual(utm, { source: "ig", medium: "social", campaign: null, content: "link_in_bio", meta_click: true });
  assert.equal(JSON.stringify(utm).includes("PAdGRle"), false);
});

test("our ad link's tags are lowercased and anything unexpected is dropped", () => {
  assert.deepEqual(
    readUtm("?utm_source=Instagram&utm_medium=paid_social&utm_campaign=2026-11-ML-Reel&utm_content=reel%204035"),
    { source: "instagram", medium: "paid_social", campaign: "2026-11-ml-reel", content: null, meta_click: false },
  );
  assert.deepEqual(readUtm(`?utm_source=${"x".repeat(65)}&utm_medium=%3Cb%3E`), {
    source: null,
    medium: null,
    campaign: null,
    content: null,
    meta_click: false,
  });
});

test("a ref has six letters a person can't misread", () => {
  for (let index = 0; index < 50; index += 1) assert.match(newRef(), REF_PATTERN);
  assert.equal(newRef((bytes) => bytes.fill(0)), "222222");
  assert.equal(newRef((bytes) => bytes.fill(255)), "ZZZZZZ");
});

test("each page language prefills its own greeting, with the ref FinBoy removes", () => {
  assert.equal(greeting("ml", "K7Q2MX"), "നമസ്കാരം FinBoy (ref K7Q2MX)");
  assert.equal(greeting("en", "K7Q2MX"), "Hi FinBoy (ref K7Q2MX)");
  assert.equal(greeting("hi", null), "नमस्ते FinBoy");
  assert.equal(greeting("en", "K7Q2MO"), "Hi FinBoy");
});

test("recording a visit and a tap never throws and sends no click ID", async () => {
  const sent: { url: string; body: unknown; keepalive: boolean | undefined }[] = [];
  globalThis.fetch = async (url, init) => {
    sent.push({ url: String(url), body: JSON.parse(String(init?.body)), keepalive: init?.keepalive });
    throw new TypeError("offline");
  };
  await recordVisit({ ref: "K7Q2MX", landing: "/ml", language: "ml", ...readUtm(BIO_LINK) });
  tapVisit("K7Q2MX");
  tapVisit("not-a-ref");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(
    sent.map(({ url, keepalive }) => [new URL(url).pathname, keepalive]),
    [
      ["/api/v1/visits", true],
      ["/api/v1/visits/tap", true],
    ],
  );
  assert.equal(JSON.stringify(sent).includes("PAdGRle"), false);
  assert.deepEqual(sent[1]?.body, { ref: "K7Q2MX" });
});
