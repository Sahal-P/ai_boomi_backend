import assert from "node:assert/strict";
import { test } from "node:test";
import { ApiError } from "./http.ts";
import { getHealth } from "./health.ts";

const healthy = {
  service: "finboy-api",
  version: "0.1.0",
  status: "ok",
  database: "connected",
};

test("health client calls the configured backend without credentials or caching", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async (input: string, init: RequestInit) => {
      assert.equal(input, "http://127.0.0.1:8000/api/v1/health");
      assert.equal(init.cache, "no-store");
      assert.equal(init.credentials, "omit");
      assert.ok(init.signal instanceof AbortSignal);
      return Response.json(healthy);
    },
  );
  assert.deepEqual(await getHealth(), healthy);
});

test("health client accepts a real database outage as degraded", async (t) => {
  const degraded = { ...healthy, status: "degraded", database: "unavailable" };
  t.mock.method(globalThis, "fetch", async () =>
    Response.json(degraded, { status: 503 }),
  );
  assert.deepEqual(await getHealth(), degraded);
});

test("health client rejects malformed or inconsistent success payloads", async (t) => {
  for (const value of [
    {},
    { ...healthy, database: "unavailable" },
    { ...healthy, service: "other" },
  ]) {
    t.mock.method(globalThis, "fetch", async () => Response.json(value));
    await assert.rejects(getHealth(), ApiError);
  }
});

test("health client rejects unexpected HTTP statuses and non-JSON data", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("private-error", { status: 500 }),
  );
  await assert.rejects(
    getHealth(),
    (error: unknown) =>
      error instanceof ApiError &&
      error.status === 500 &&
      !error.message.includes("private-error"),
  );
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("<html>unavailable</html>"),
  );
  await assert.rejects(getHealth(), ApiError);
});

test("health client propagates an unreachable backend", async (t) => {
  t.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("Network error");
  });
  await assert.rejects(getHealth(), TypeError);
});

test("health client rejects status/body mismatches in both directions", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json(healthy, { status: 503 }));
  await assert.rejects(getHealth(), ApiError);
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ ...healthy, status: "degraded", database: "unavailable" }));
  await assert.rejects(getHealth(), ApiError);
});
