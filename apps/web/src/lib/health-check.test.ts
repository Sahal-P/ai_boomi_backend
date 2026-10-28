import assert from "node:assert/strict";
import { test } from "node:test";
import type { HealthResponse } from "./api/health.ts";
import { checkHealth } from "./health-check.ts";

const ok: HealthResponse = {
  service: "finboy-api",
  version: "0.1.0",
  status: "ok",
  database: "connected",
};

function answers(...outcomes: (HealthResponse | Error)[]) {
  let calls = 0;
  const get = async (): Promise<HealthResponse> => {
    const outcome = outcomes[calls++];
    if (outcome === undefined) throw new Error("checked more often than expected");
    if (outcome instanceof Error) throw outcome;
    return outcome;
  };
  return { get, calls: () => calls };
}

test("one missed check is retried and does not count as unreachable", async () => {
  const health = answers(new Error("lost"), ok);
  assert.deepEqual(await checkHealth(health.get, new AbortController().signal, 1), ok);
  assert.equal(health.calls(), 2);
});

test("two missed checks in a row mean unreachable", async () => {
  const health = answers(new Error("lost"), new Error("lost again"));
  assert.equal(await checkHealth(health.get, new AbortController().signal, 1), null);
  assert.equal(health.calls(), 2);
});

test("a healthy first answer is not checked again", async () => {
  const health = answers(ok);
  assert.deepEqual(await checkHealth(health.get, new AbortController().signal, 1), ok);
  assert.equal(health.calls(), 1);
});

test("cancelling while waiting to retry stops without another request", async () => {
  const controller = new AbortController();
  const health = answers(new Error("lost"), ok);
  const pending = checkHealth(health.get, controller.signal, 10_000);
  await new Promise((resolve) => setTimeout(resolve, 0));
  controller.abort();
  await assert.rejects(pending, { name: "AbortError" });
  assert.equal(health.calls(), 1);
});
