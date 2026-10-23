import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { z } from "zod";
import {
  getSummary,
  inputPaise,
  simulationSchema,
  summarySchema,
  transactionSchema,
} from "./money.ts";
import { detailSchema, reviewTransaction } from "./transactions.ts";
import { answerSchema, speechFor, transcribeAudio } from "./assistant.ts";

const examples: z.infer<ReturnType<typeof z.record>> = z
  .record(z.string(), z.unknown())
  .parse(
    JSON.parse(
      await readFile(
        new URL(
          "../../../../../docs/handoffs/agent-1-api-examples.json",
          import.meta.url,
        ),
        "utf8",
      ),
    ),
  );

test("product schemas accept actual PostgreSQL HTTP examples and preserve integer paise", () => {
  assert.equal(
    summarySchema.parse(examples.money_summary).estimated_unallocated_minor,
    1478000,
  );
  assert.equal(
    z.array(transactionSchema).parse(examples.transactions).length,
    26,
  );
  assert.equal(
    detailSchema.parse(examples.transaction_detail).sources.length,
    3,
  );
  assert.equal(
    simulationSchema.parse(examples.simulation).remaining_after_proposal_minor,
    978000,
  );
  assert.throws(() =>
    summarySchema.parse({
      ...summarySchema.parse(examples.money_summary),
      tracked_income_minor: 12.5,
    }),
  );
  assert.equal(inputPaise("5000.05"), 500005);
  for (const invalid of ["-1", "1e3", "0", "10.999", "NaN", ""])
    assert.equal(inputPaise(invalid), null);
});

test("typed summary client rejects malformed success without exposing it", async (t) => {
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ private: "sensitive" }),
  );
  await assert.rejects(
    getSummary(),
    (error) => error instanceof Error && !error.message.includes("sensitive"),
  );
});

test("merge request follows frozen keep_id contract and omits credentials", async (t) => {
  const detail = detailSchema.parse(examples.transaction_detail);
  t.mock.method(
    globalThis,
    "fetch",
    async (input: string, init: RequestInit) => {
      assert.ok(
        input.endsWith(`/api/v1/transactions/${detail.transaction.id}/merge`),
      );
      assert.equal(init.method, "POST");
      assert.equal(init.credentials, "omit");
      assert.deepEqual(JSON.parse(String(init.body)), {
        keep_id: detail.transaction.id,
      });
      return Response.json(detail);
    },
  );
  await reviewTransaction(
    detail.transaction.id,
    "merge",
    detail.transaction.id,
  );
});

test("speech failure never turns JSON error into playable audio", async (t) => {
  const answer = answerSchema.parse({
    intent: "clarification",
    policy: "clarify",
    display_text: "Please clarify.",
    speech_text: "Please clarify.",
    speech_language: "en",
    facts: [],
    simulation: null,
    evidence_transactions: [],
    warnings: [],
  });
  t.mock.method(globalThis, "fetch", async () =>
    Response.json({ error: "private" }, { status: 503 }),
  );
  await assert.rejects(speechFor(answer));
  assert.equal(answer.display_text, "Please clarify.");
});

test("transcription uses bounded multipart audio and validates detected language", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async (_input: string, init: RequestInit) => {
      assert.ok(init.body instanceof FormData);
      assert.ok(init.body.get("audio") instanceof Blob);
      assert.equal(init.credentials, "omit");
      return Response.json({
        transcript: "synthetic",
        detected_language: "ml",
      });
    },
  );
  assert.equal(
    (await transcribeAudio(new Blob(["synthetic"], { type: "audio/webm" })))
      .detected_language,
    "ml",
  );
  assert.throws(() =>
    transcribeAudio(new Blob([new Uint8Array(3 * 1024 * 1024 + 1)])),
  );
});
