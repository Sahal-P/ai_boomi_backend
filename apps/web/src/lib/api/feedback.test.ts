import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { deleteFeedback, listFeedback, screenFrom, sendFeedback } from "./feedback.ts";
import { ApiError } from "./http.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

type Seen = { url: string; init: RequestInit | undefined };
function answer(status: number, body: unknown, seen: Seen[] = []) {
  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    seen.push({ url: String(url), init });
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
  return seen;
}

const item = {
  id: "0b3f8a52-6c1e-4d8f-9a7b-2f4c6e8a1d3b",
  kind: "problem",
  message: "The date was wrong",
  page: "/review",
  status: "planned",
  has_screenshot: true,
  created_at: "2026-11-22T09:30:00+00:00",
  status_changed_at: "2026-11-22T10:00:00+00:00",
};

test("only an app path is sent as the screen", () => {
  assert.equal(screenFrom("/transactions?tab=review#row"), "/transactions");
  for (const unsafe of [null, "", "https://evil.test/x", "//evil.test", "/\\evil.test", "review", "/feedback"]) {
    assert.equal(screenFrom(unsafe), "", String(unsafe));
  }
  assert.equal(screenFrom(`/${"p".repeat(300)}`).length, 200);
});

test("sending trims the message, keeps the screen path and leaves out a missing screenshot", async () => {
  const seen = answer(201, { item, screenshot_saved: false });
  const sent = await sendFeedback({ kind: "problem", message: "  The date was wrong \n", page: "/review?x=1", screenshot: null });
  assert.equal(sent.item.status, "planned");
  assert.equal(seen[0]?.init?.method, "POST");
  assert.deepEqual(JSON.parse(String(seen[0]?.init?.body)), { kind: "problem", message: "The date was wrong", page: "/review" });
});

test("a screenshot goes as its type and base64 bytes", async () => {
  const seen = answer(201, { item, screenshot_saved: true });
  await sendFeedback({ kind: "idea", message: "x", page: "", screenshot: { type: "image/webp", data: "UklGRg==" } });
  assert.deepEqual(JSON.parse(String(seen[0]?.init?.body)).screenshot, { type: "image/webp", data: "UklGRg==" });
});

test("the daily limit and unexpected replies are reported, not shown", async () => {
  answer(429, { error: { code: "feedback_limit", request_id: "r1" } });
  await assert.rejects(sendFeedback({ kind: "idea", message: "x", page: "", screenshot: null }), (error: unknown) => {
    assert.ok(error instanceof ApiError && error.code === "feedback_limit" && error.kind === "rate_limited");
    return true;
  });
  answer(200, { screenshots: true, items: [{ ...item, status: "closed" }] });
  await assert.rejects(listFeedback(), (error: unknown) => error instanceof ApiError && error.kind === "invalid_response");
});

test("listing and deleting use the household's own routes", async () => {
  const seen = answer(200, { screenshots: false, items: [item] });
  const listed = await listFeedback();
  assert.equal(listed.items[0]?.kind, "problem");
  assert.match(seen[0]?.url ?? "", /\/api\/v1\/feedback$/);
  answer(204, null, seen);
  await deleteFeedback(item.id);
  assert.equal(seen[1]?.init?.method, "DELETE");
  assert.match(seen[1]?.url ?? "", new RegExp(`/api/v1/feedback/${item.id}$`));
  answer(404, { error: { code: "feedback_not_found" } });
  await assert.rejects(deleteFeedback(item.id), (error: unknown) => error instanceof ApiError && error.kind === "not_found");
});
