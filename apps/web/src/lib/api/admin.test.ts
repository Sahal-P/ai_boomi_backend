import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { actOnHousehold, adminSignIn, getHousehold, listHouseholds, safeAdminReturnPath } from "./admin.ts";
import { ApiError } from "./http.ts";
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

test("household search keeps empty filters out of the URL", async () => {
  const seen = answer(200, { items: [], total: 0, offset: 0, next_offset: null }, []);
  const result = await listHouseholds({ q: "  98123 45670  ", kind: null, status: "suspended", offset: 0 });
  assert.equal(result.total, 0);
  assert.match(seen[0]?.url ?? "", /\/api\/v1\/admin\/households\?q=98123\+45670&status=suspended$/);
});
