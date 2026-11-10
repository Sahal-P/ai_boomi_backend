import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { askLink, getForYou } from "./coach.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

function serve(body: unknown) {
  const urls: string[] = [];
  globalThis.fetch = async (url) => {
    urls.push(String(url).replace(/^.*\/api\/v1/, ""));
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  return urls;
}

const item = {
  kind: "budget_near",
  tone: "warning",
  title: "Budget running low",
  text: "Food & dining: ₹4,200 of your ₹5,000 budget spent, ₹800 left with 13 days to go.",
  href: "#budgets-title",
  ask: "How can I spend less on food & dining?",
};

test("For you reads the coach's items and whether WhatsApp gets them", async () => {
  const urls = serve({
    items: [item, { ...item, kind: "unusual_payment", href: "/transactions?selected=3f2a6a5e-6f7b-4d43-9a3b-2b8f0f4c9d10" }],
    whatsapp: "off",
  });
  const found = await getForYou();
  assert.deepEqual(urls, ["/coach"]);
  assert.equal(found.items.length, 2);
  assert.equal(found.whatsapp, "off");
});

test("an item may only link inside FinBoy", async () => {
  for (const href of ["https://example.com", "javascript:alert(1)", "//example.com/x"]) {
    serve({ items: [{ ...item, href }], whatsapp: "none" });
    await assert.rejects(getForYou());
  }
});

test("Ask opens with the item's question typed in", () => {
  assert.equal(askLink("How can I spend less on food & dining?"), "/assistant?ask=How%20can%20I%20spend%20less%20on%20food%20%26%20dining%3F");
});
