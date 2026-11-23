import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import {
  actOnHousehold,
  adminSignIn,
  getGrowth,
  getHousehold,
  getMessageMedia,
  getMessages,
  getSignups,
  listHouseholds,
  MEDIA_LIMIT,
  safeAdminReturnPath,
} from "./admin.ts";
import { ApiError } from "./http.ts";
import { formatPhone } from "../admin-labels.ts";
import { onSessionEvent } from "../session-events.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

type Seen = { url: string; init: RequestInit | undefined };
function answer(status: number, body: unknown, seen: Seen[] = []) {
  globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
    seen.push({ url: String(url), init });
    return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
  return seen;
}

test("admin sign-in returns only to admin pages", () => {
  assert.equal(safeAdminReturnPath("/admin/households?selected=abc&q=91"), "/admin/households?selected=abc&q=91");
  assert.equal(safeAdminReturnPath("/admin"), "/admin");
  for (const unsafe of [
    null,
    "",
    "/dashboard",
    "/admin/login",
    "/adminx",
    "https://evil.example/admin",
    "//evil.example/admin",
    "/\\evil.example",
    "/admin/../api/v1/admin/logout",
    `/admin?${"x".repeat(600)}`,
  ]) {
    assert.equal(safeAdminReturnPath(unsafe), "/admin", String(unsafe));
  }
});

test("a wrong admin password is not a lost session", async () => {
  let expired = 0;
  const stop = onSessionEvent("expired", () => {
    expired += 1;
  });
  answer(401, { error: { code: "admin_login_failed", request_id: "r1" } });
  await assert.rejects(adminSignIn("admin@example.test", "wrong"), (error: unknown) => {
    assert.ok(error instanceof ApiError && error.code === "admin_login_failed");
    return true;
  });
  assert.equal(expired, 0);
  answer(401, { error: { code: "admin_required", request_id: "r2" } });
  await assert.rejects(getHousehold("10000000-0000-4000-8000-000000000001"));
  assert.equal(expired, 1);
  stop();
});

test("writes always send a small JSON body and only IDs go into paths", async () => {
  const seen = answer(200, {}, []);
  await assert.rejects(actOnHousehold("../../auth/logout", "suspend"), (error: unknown) => {
    assert.ok(error instanceof ApiError && error.kind === "validation");
    return true;
  });
  assert.equal(seen.length, 0);
  await assert.rejects(actOnHousehold("00000000-0000-0000-0000-000000000001", "suspend")); // invalid reply
  assert.equal(seen[0]?.init?.method, "POST");
  assert.equal(seen[0]?.init?.body, "{}");
  assert.match(seen[0]?.url ?? "", /\/api\/v1\/admin\/households\/00000000-0000-0000-0000-000000000001\/suspend$/);
});

test("a household row says who it is: name and phone digits, or null", async () => {
  const row = {
    id: "10000000-0000-4000-8000-000000000001",
    short_id: "10000000",
    name: "Asha Menon",
    phone: "919812345670",
    kind: "self_serve",
    status: "active",
    whatsapp: true,
    google: false,
    joined_at: "2026-11-18T10:00:00Z",
    agreed_at: "2026-11-18T10:00:00Z",
    last_active_at: null,
    plan: "included",
    language: "ml",
  };
  answer(200, { items: [row, { ...row, name: null, phone: null }], total: 2, offset: 0, next_offset: null });
  const page = await listHouseholds({});
  assert.deepEqual(
    page.items.map((item) => [item.name, item.phone]),
    [["Asha Menon", "919812345670"], [null, null]],
  );
  answer(200, { items: [{ ...row, phone: "+91 98123" }], total: 1, offset: 0, next_offset: null });
  await assert.rejects(listHouseholds({}), { kind: "invalid_response" });
});

test("phone numbers read the way people write them", () => {
  assert.equal(formatPhone("919812345670"), "+91 98123 45670");
  assert.equal(formatPhone("447700900123"), "+447700900123");
});

test("household search keeps empty filters out of the URL", async () => {
  const seen = answer(200, { items: [], total: 0, offset: 0, next_offset: null }, []);
  const result = await listHouseholds({ q: "  98123 45670  ", kind: null, status: "suspended", offset: 0 });
  assert.equal(result.total, 0);
  assert.match(seen[0]?.url ?? "", /\/api\/v1\/admin\/households\?q=98123\+45670&status=suspended$/);
});

const HOUSEHOLD = "10000000-0000-4000-8000-000000000001";
const MESSAGE = "20000000-0000-4000-8000-000000000002";
const kept = {
  id: MESSAGE,
  at: "2026-11-22T09:30:00+00:00",
  channel: "whatsapp",
  direction: "in",
  kind: "voice",
  text: null,
  transcript: "doodhwale ko 500 diye",
  language: "hi",
  choices: [],
  media: "audio",
  media_bytes: 4096,
  status: null,
  outcome: null,
};
const invalid = (kind: string) => (error: unknown) => error instanceof ApiError && error.kind === kind;
const file = (body: BodyInit, type: string) =>
  (async () => new Response(body, { headers: { "content-type": type } })) as typeof fetch;

test("kept messages are validated and continue from the oldest one shown", async () => {
  const cursor = `${kept.at}|${MESSAGE}`;
  const seen = answer(200, { kept_from: kept.at, declined_at: null, items: [kept], next_before: cursor });
  const page = await getMessages(HOUSEHOLD, cursor);
  assert.equal(page.items[0]?.transcript, "doodhwale ko 500 diye");
  assert.equal(page.next_before, cursor);
  assert.match(seen[0]?.url ?? "", /\/households\/10000000-0000-4000-8000-000000000001\/messages\?before=2026-11-22T09%3A30%3A00%2B00%3A00%7C20000000-/);
  answer(200, { kept_from: null, declined_at: null, items: [{ ...kept, kind: "secret" }], next_before: null });
  await assert.rejects(getMessages(HOUSEHOLD, null), invalid("invalid_response"));
  await assert.rejects(getMessages("../admins", null), invalid("validation"));
});

test("a kept file opens only as audio or an image within the size limit", async () => {
  globalThis.fetch = file(new Uint8Array([1, 2, 3]), "audio/ogg");
  assert.equal((await getMessageMedia(MESSAGE)).size, 3);
  globalThis.fetch = file("<html>", "text/html");
  await assert.rejects(getMessageMedia(MESSAGE), invalid("invalid_response"));
  globalThis.fetch = file(new Uint8Array(MEDIA_LIMIT + 1), "image/jpeg");
  await assert.rejects(getMessageMedia(MESSAGE), invalid("invalid_response"));
  answer(503, { error: { code: "media_unavailable", request_id: "r3" } });
  await assert.rejects(getMessageMedia(MESSAGE), (error: unknown) => error instanceof ApiError && error.code === "media_unavailable");
});

const signups = {
  enabled: true,
  open: true,
  agreed: 14,
  pending: 4,
  limit: 100,
  waitlist: 0,
  waitlist_languages: {},
  oldest_waiting_since: null,
  stale_pending: 0,
};
const reel = {
  source: "instagram",
  medium: "paid_social",
  campaign: "2026-11-ml-reel",
  direct: false,
  opened: 283,
  tapped: 40,
  signed_up: 15,
  agreed: 11,
  first_record: 6,
  minutes_to_tap: 0.8,
  minutes_to_sign_up: 1.5,
  minutes_to_record: 7,
};

test("where sign-ups came from is read for the chosen period, and an older API shows none", async () => {
  const seen = answer(200, { ...signups, sources: [reel], sources_days: 7 });
  const result = await getSignups(undefined, 7);
  assert.match(seen[0]?.url ?? "", /\/api\/v1\/admin\/signups\?days=7$/);
  assert.deepEqual(result.sources, [reel]);
  answer(200, signups);
  assert.deepEqual((await getSignups()).sources, []);
  // Tags are only what FinBoy keeps: no click IDs or free text.
  answer(200, { ...signups, sources: [{ ...reel, campaign: "IwAR0 click id" }], sources_days: 30 });
  await assert.rejects(getSignups(), invalid("invalid_response"));
});

const growth = {
  period: "12w",
  unit: "week",
  cohort_unit: "week",
  today: "2026-11-24",
  summary: {
    joined: 11,
    joined_before: 4,
    left: 1,
    households: 14,
    active_week: 9,
    activated: 6,
    minutes_to_record: 4.5,
  },
  points: [
    {
      start: "2026-11-23",
      end: "2026-11-29",
      partial: true,
      joined: 3,
      left: 0,
      households: 14,
      active: 9,
      records: 41,
      recording: 7,
    },
  ],
  funnel: {
    opened: 363,
    tapped: 48,
    signed_up: 15,
    agreed: 11,
    first_record: 6,
    direct_signed_up: 2,
    direct_agreed: 2,
    direct_first_record: 1,
  },
  cohorts: [{ start: "2026-11-16", households: 5, active: [5, 3] }],
};

test("growth is read for its period, as counts and calendar days only", async () => {
  const seen = answer(200, growth);
  const result = await getGrowth("12w");
  assert.match(seen[0]?.url ?? "", /\/api\/v1\/admin\/growth\?period=12w$/);
  assert.equal(result.points[0]?.partial, true);
  assert.deepEqual(result.cohorts[0]?.active, [5, 3]);
  // Anything else is refused: a time where a day belongs, a negative count or another period.
  for (const wrong of [
    { ...growth, today: "2026-11-24T10:00:00Z" },
    { ...growth, summary: { ...growth.summary, joined: -1 } },
    { ...growth, period: "7d" },
  ]) {
    answer(200, wrong);
    await assert.rejects(getGrowth("12w"), invalid("invalid_response"));
  }
});
