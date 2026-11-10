import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { answerSchema, askQuestion, askQuestionStream, getThread, listThreads, readEvents } from "./assistant.ts";
import { ApiError } from "./http.ts";
import { deleteMemories, editMemory, listMemories, setMemoryEnabled } from "./memory.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

const THREAD = "3f2a6a5e-6f7b-4d43-9a3b-2b8f0f4c9d10";
const MEMORY = "7c9e6679-7425-40de-944b-e07fc1f90ae7";
const answer = {
  intent: "advisor",
  policy: "answer",
  display_text: "Food this month is ₹4,200.",
  speech_text: "Food this month is ₹4,200.",
  speech_language: "en",
  display_language: "en",
  display_script: "Latn",
  facts: [],
  simulation: null,
  evidence_transactions: [],
  evidence_total: 0,
  evidence_sampled: false,
  warnings: [],
  warning_labels: {},
  data_version: "7:2026-11-07",
  dataset: "household",
  resolved_period: null,
};

function record(body: unknown, status = 200) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  globalThis.fetch = async (url, init) => {
    calls.push({
      url: String(url).replace(/^.*\/api\/v1/, ""),
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

test("an answer from before the advisor still parses, with empty advisor fields", () => {
  const parsed = answerSchema.parse(answer);
  assert.equal(parsed.thread_id, null);
  assert.deepEqual([parsed.memory_changes, parsed.follow_ups], [[], []]);
  const advised = answerSchema.parse({
    ...answer,
    thread_id: THREAD,
    memory_changes: [{ action: "saved", text: "Saving for a bike", id: MEMORY }],
    follow_ups: ["And last month?"],
  });
  assert.equal(advised.memory_changes[0]?.action, "saved");
  assert.equal(answerSchema.safeParse({ ...answer, memory_changes: [{ action: "kept", text: "x" }] }).success, false);
});

test("a question continues its chat only when there is one", async () => {
  const calls = record(answer);
  await askQuestion("Food?", "en");
  await askQuestion("And last month?", "en", undefined, THREAD);
  assert.deepEqual(
    calls.map((call) => (call.body as { thread_id?: string }).thread_id ?? null),
    [null, THREAD],
  );
});

test("chats are listed and opened through the household's own routes", async () => {
  const thread = {
    id: THREAD,
    channel: "whatsapp",
    title: "Food this month?",
    started_at: "2026-11-07T04:30:00Z",
    last_at: "2026-11-07T04:31:00+00:00",
    messages: 2,
  };
  record({ threads: [thread] });
  assert.equal((await listThreads())[0]?.channel, "whatsapp");
  const calls = record({
    thread,
    messages: [
      { id: MEMORY, role: "user", text: "Food?", language: "en", created_at: "2026-11-07T04:30:00Z" },
    ],
  });
  assert.equal((await getThread(THREAD)).messages.length, 1);
  assert.equal(calls[0]?.url, `/assistant/threads/${THREAD}`);
});

test("memory is read, edited, switched off and cleared", async () => {
  const memory = {
    id: MEMORY,
    kind: "goal",
    text: "Saving for a bike",
    source: "web",
    created_at: "2026-11-07T04:30:00Z",
    updated_at: "2026-11-07T04:30:00Z",
  };
  record({ enabled: true, limit: 80, memories: [memory], chats: 3 });
  assert.equal((await listMemories()).memories[0]?.kind, "goal");
  let calls = record({ ...memory, text: "Saving for a car" });
  await editMemory(MEMORY, "Saving for a car");
  assert.deepEqual(calls[0], { url: `/memory/${MEMORY}`, method: "PATCH", body: { text: "Saving for a car" } });
  calls = record({ enabled: false });
  await setMemoryEnabled(false);
  assert.deepEqual(calls[0], { url: "/memory/settings", method: "PUT", body: { enabled: false } });
  calls = record({ deleted: 1 });
  assert.equal((await deleteMemories()).deleted, 1);
  assert.equal(calls[0]?.method, "DELETE");
});

/** A streamed response whose bytes arrive in pieces, cut at the given byte offsets. */
function stream(text: string, cuts: number[] = []) {
  const calls: { url: string; accept: string | null; body: unknown }[] = [];
  globalThis.fetch = async (url, init) => {
    calls.push({
      url: String(url).replace(/^.*\/api\/v1/, ""),
      accept: new Headers(init?.headers).get("Accept"),
      body: JSON.parse(String(init?.body)),
    });
    const bytes = new TextEncoder().encode(text);
    const edges = [0, ...cuts, bytes.length];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (let index = 1; index < edges.length; index += 1) {
          controller.enqueue(bytes.slice(edges[index - 1], edges[index]));
        }
        controller.close();
      },
    });
    return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  };
  return calls;
}

const event = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

test("server-sent events are read whole, keeping an unfinished one for the next piece", () => {
  const { events, rest } = readEvents('event: progress\ndata: {"stage":"dues"}\n\nevent: answer\ndata: {"a"');
  assert.deepEqual(events, [{ event: "progress", data: '{"stage":"dues"}' }]);
  assert.equal(rest, 'event: answer\ndata: {"a"');
});

test("a streamed question hears each step, then its answer with its guides", async () => {
  const source = { id: "pm-kisan", title: "PM-KISAN", url: "https://pmkisan.gov.in" };
  const text =
    event("progress", { stage: "thinking" }) +
    event("progress", { stage: "search_knowledge" }) +
    event("progress", { stage: "Not A Stage" }) +
    event("answer", { ...answer, thread_id: THREAD, sources: [source] });
  const rupee = new TextEncoder().encode(text).indexOf(0xe2); // cut inside "₹"
  const calls = stream(text, [7, 40, rupee + 1]);
  const stages: string[] = [];
  const result = await askQuestionStream("PM-KISAN?", "en", {
    onProgress: (stage) => stages.push(stage),
    threadId: THREAD,
  });
  assert.deepEqual(stages, ["thinking", "search_knowledge"]);
  assert.equal(result.display_text, "Food this month is ₹4,200.");
  assert.deepEqual(result.sources, [source]);
  assert.deepEqual(calls, [
    {
      url: "/assistant/ask/stream",
      accept: "text/event-stream",
      body: { text: "PM-KISAN?", display_style: "en", include_overdue_line: true, thread_id: THREAD },
    },
  ]);
});

test("an error event is a classified failure; a stream that ends early is unexpected", async () => {
  stream(
    event("progress", { stage: "thinking" }) +
      event("error", {
        status: 503,
        error: { code: "assistant_unavailable", message: "Internal words", request_id: "req-1" },
      }),
  );
  await assert.rejects(
    askQuestionStream("Food?", "en", { onProgress: () => undefined }),
    (error: unknown) =>
      error instanceof ApiError &&
      error.kind === "unavailable" &&
      error.code === "assistant_unavailable" &&
      error.requestId === "req-1",
  );
  stream(event("progress", { stage: "thinking" }));
  await assert.rejects(
    askQuestionStream("Food?", "en", { onProgress: () => undefined }),
    (error: unknown) => error instanceof ApiError && error.kind === "invalid_response",
  );
});

test("a refusal before the stream starts is an ordinary failure", async () => {
  record({ error: { code: "usage_limit", message: "Limit", request_id: "req-2" } }, 429);
  await assert.rejects(
    askQuestionStream("Food?", "en", { onProgress: () => undefined }),
    (error: unknown) => error instanceof ApiError && error.kind === "rate_limited" && error.code === "usage_limit",
  );
});

test("guide links must be https", () => {
  for (const url of ["javascript:alert(1)", "http://pmkisan.gov.in", "not a url"]) {
    const parsed = answerSchema.safeParse({ ...answer, sources: [{ id: "pm-kisan", title: "PM-KISAN", url }] });
    assert.equal(parsed.success, false, url);
  }
  const plain = answerSchema.parse({ ...answer, sources: [{ id: "budgeting-basics", title: "Budgeting" }] });
  assert.equal(plain.sources[0]?.url, null);
});
