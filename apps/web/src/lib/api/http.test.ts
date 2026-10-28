import assert from "node:assert/strict";
import { test } from "node:test";
import { z } from "zod";
import { ApiError, apiCredentials, requestJson } from "./http.ts";

const schema = z.object({ count: z.number().int() });

test("requestJson validates responses; a plain-HTTP API gets no credentials or caching", async (t) => {
  t.mock.method(globalThis, "fetch", async (input: string, init: RequestInit) => {
    assert.equal(input, "http://127.0.0.1:8000/api/v1/example");
    assert.equal(init.method, "POST");
    assert.equal(init.credentials, "omit");
    assert.equal(init.cache, "no-store");
    assert.equal(new Headers(init.headers).get("Content-Type"), "application/json");
    return Response.json({ count: 3 });
  });
  assert.deepEqual(await requestJson("/api/v1/example", schema, {
    method: "POST", credentials: "include", cache: "force-cache",
    headers: { "Content-Type": "application/json" }, body: "{}",
  }), { count: 3 });
});

test("requestJson rejects invalid JSON schemas without exposing input", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ count: "private-value" }));
  await assert.rejects(requestJson("/api/v1/example", schema), (error: unknown) =>
    error instanceof ApiError && error.status === 200 && !error.message.includes("private"));
});

test("requestJson classifies timeouts and keeps caller cancellation as AbortError", async (t) => {
  t.mock.method(globalThis, "fetch", async (_input: string, init: RequestInit) => {
    const signal = init.signal;
    assert.ok(signal);
    signal.throwIfAborted();
    return new Promise<Response>((_resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Timeout did not abort")), 100);
      signal.addEventListener("abort", () => {
        clearTimeout(timer);
        reject(signal.reason);
      }, { once: true });
    });
  });
  await assert.rejects(requestJson("/api/v1/example", schema, { timeoutMs: 5 }), (error: unknown) =>
    error instanceof ApiError && error.kind === "timeout");
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(requestJson("/api/v1/example", schema, { signal: controller.signal }), {
    name: "AbortError",
  });
});

test("requestJson rejects external paths", async () => {
  await assert.rejects(requestJson("//untrusted.example", schema), ApiError);
});

test("same-origin production proxy sends only first-party cookies", async (t) => {
  const previous = process.env.NEXT_PUBLIC_API_URL;
  process.env.NEXT_PUBLIC_API_URL = "/";
  t.after(() => {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = previous;
  });
  t.mock.method(globalThis, "fetch", async (input: string, init: RequestInit) => {
    assert.equal(input, "/api/v1/example");
    assert.equal(init.credentials, "same-origin");
    assert.equal(init.cache, "no-store");
    return Response.json({ count: 3 });
  });
  assert.deepEqual(await requestJson("/api/v1/example", schema), { count: 3 });
});

test("the deployed HTTPS API is called directly with the household cookie", async (t) => {
  const previous = process.env.NEXT_PUBLIC_API_URL;
  process.env.NEXT_PUBLIC_API_URL = "https://finboy-api.antlegs.in";
  t.after(() => {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = previous;
  });
  t.mock.method(globalThis, "fetch", async (input: string, init: RequestInit) => {
    assert.equal(input, "https://finboy-api.antlegs.in/api/v1/example");
    assert.equal(init.credentials, "include");
    assert.equal(init.cache, "no-store");
    return Response.json({ count: 3 });
  });
  assert.deepEqual(await requestJson("/api/v1/example", schema), { count: 3 });
});

test("credentials: same-origin for the proxy, include for HTTPS, none for plain HTTP", () => {
  assert.equal(apiCredentials(""), "same-origin");
  assert.equal(apiCredentials("https://finboy-api.antlegs.in"), "include");
  assert.equal(apiCredentials("http://127.0.0.1:8000"), "omit");
});
