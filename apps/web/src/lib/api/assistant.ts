import { z } from "zod";
import { ApiError, apiFetch, failure, jsonBody, requestJson } from "./http.ts";
import { baseTransactionSchema, opaque, simulationSchema, transactionSchema } from "./money.ts";

export const styles = ["auto", "en", "hi", "hinglish", "ml", "manglish"] as const;
export type DisplayStyle = (typeof styles)[number];
export type Language = "en" | "hi" | "ml";

// Evidence keeps the phase-1 fields; contract provenance fields are used when present.
const evidenceSchema = baseTransactionSchema.extend(
  transactionSchema
    .pick({ source_modes: true, source_count: true, dataset: true })
    .partial().shape,
);

export const answerSchema = z.object({
  intent: z.string(),
  policy: z.enum(["answer", "decline", "clarify"]),
  display_text: z.string(),
  speech_text: z.string(),
  speech_language: z.enum(["en", "hi", "ml"]),
  display_language: z.enum(["en", "hi", "ml"]),
  display_script: z.enum(["Latn", "Deva", "Mlym"]),
  facts: z.array(
    z.object({
      key: z.string(),
      label: z.string().min(1),
      amount_minor: z.number().int().nullable(),
      count: z.number().int().nullable(),
      currency: z.literal("INR").nullable(),
    }),
  ),
  simulation: simulationSchema.nullable(),
  evidence_transactions: z.array(evidenceSchema),
  evidence_total: z.number().int().nonnegative(),
  evidence_sampled: z.boolean(),
  warnings: z.array(z.string()),
  warning_labels: z.record(z.string(), z.string()),
  data_version: opaque,
  dataset: z.literal("household"),
  resolved_period: z
    .object({ start: z.iso.date(), end: z.iso.date(), label: z.string().min(1) })
    .nullable(),
  // Advisor round (additive): the chat this answer belongs to, memory changes and follow-ups.
  thread_id: z.uuid().nullable().default(null),
  memory_changes: z
    .array(
      z.object({
        action: z.enum(["saved", "updated", "forgotten"]),
        text: z.string(),
        id: z.uuid().nullable().default(null),
      }),
    )
    .default([]),
  follow_ups: z.array(z.string()).default([]),
  // Advisor phase 2: the reviewed FinBoy guides an answer is based on, with their official site.
  sources: z
    .array(
      z.object({
        id: z.string().regex(/^[a-z0-9-]{1,64}$/),
        title: z.string().min(1),
        url: z.url({ protocol: /^https$/ }).nullable().default(null),
      }),
    )
    .default([]),
});
export type Answer = z.infer<typeof answerSchema>;
export type MemoryChange = Answer["memory_changes"][number];
export type AnswerSource = Answer["sources"][number];
export type Evidence = z.infer<typeof evidenceSchema>;

/** BCP 47 tag for displayed text, so romanized Hindi/Malayalam is not announced as native script. */
export function displayLang(answer: Pick<Answer, "display_language" | "display_script">): string {
  if (answer.display_language === "en") return "en-IN";
  return answer.display_script === "Latn"
    ? `${answer.display_language}-Latn`
    : answer.display_language;
}

/** Asks in a chat: `threadId` continues it, null starts a new one (advisor round). */
export const askQuestion = (
  text: string,
  displayStyle: DisplayStyle,
  signal?: AbortSignal,
  threadId: string | null = null,
) =>
  requestJson("/api/v1/assistant/ask", answerSchema, {
    method: "POST",
    ...jsonBody({
      text,
      display_style: displayStyle,
      include_overdue_line: true,
      ...(threadId ? { thread_id: threadId } : {}),
    }),
    signal,
    timeoutMs: 60_000,
  });

type StreamEvent = { event: string; data: string };

/** Complete server-sent events in `buffer`, and the unfinished rest to keep for the next chunk. */
export function readEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: StreamEvent[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (data.length > 0) events.push({ event, data: data.join("\n") });
  }
  return { events, rest };
}

const progressSchema = z.object({ stage: z.string().regex(/^[a-z_]{1,40}$/) });
const streamErrorSchema = z.object({
  status: z.number().int(),
  error: z.object({
    code: z.string().regex(/^[a-z0-9_.-]{1,64}$/),
    request_id: z
      .string()
      .regex(/^[A-Za-z0-9-]{1,64}$/)
      .optional(),
  }),
});

function json(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return undefined;
  }
}

/**
 * Asks like `askQuestion`, but hears each step while the advisor works ("progress" events with
 * the tool it is using), then the answer. Only while the advisor is on (advisor phase 2).
 */
export async function askQuestionStream(
  text: string,
  displayStyle: DisplayStyle,
  options: { onProgress: (stage: string) => void; signal?: AbortSignal; threadId?: string | null },
): Promise<Answer> {
  const { onProgress, signal, threadId = null } = options;
  const response = await apiFetch("/api/v1/assistant/ask/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      text,
      display_style: displayStyle,
      include_overdue_line: true,
      ...(threadId ? { thread_id: threadId } : {}),
    }),
    signal,
    timeoutMs: 60_000,
  });
  if (!response.ok) throw await failure(response);
  const unexpected = () =>
    new ApiError("FinBoy received an unexpected response.", response.status, { kind: "invalid_response" });
  if (!response.body) throw unexpected();
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    for (;;) {
      let chunk: ReadableStreamReadResult<string>;
      try {
        chunk = await reader.read();
      } catch (reason) {
        if (signal?.aborted) throw reason;
        if (reason instanceof DOMException && reason.name === "TimeoutError") {
          throw new ApiError("FinBoy took too long to respond.", undefined, { kind: "timeout" });
        }
        const offline = typeof navigator !== "undefined" && navigator.onLine === false;
        throw new ApiError("FinBoy could not be reached.", undefined, { kind: offline ? "offline" : "network" });
      }
      if (chunk.done) throw unexpected(); // the stream ended without an answer
      const { events, rest } = readEvents(buffer + chunk.value);
      buffer = rest;
      for (const item of events) {
        const data = json(item.data);
        if (item.event === "progress") {
          const step = progressSchema.safeParse(data);
          if (step.success) onProgress(step.data.stage);
        } else if (item.event === "answer") {
          const answer = answerSchema.safeParse(data);
          if (!answer.success) throw unexpected();
          return answer.data;
        } else if (item.event === "error") {
          const problem = streamErrorSchema.safeParse(data);
          if (!problem.success) throw unexpected();
          throw new ApiError("FinBoy could not complete the request.", problem.data.status, {
            code: problem.data.error.code,
            requestId: problem.data.error.request_id,
          });
        }
      }
    }
  } finally {
    reader.cancel().catch(() => undefined);
  }
}

const threadSchema = z.object({
  id: z.uuid(),
  channel: z.enum(["web", "whatsapp"]),
  title: z.string(),
  started_at: z.iso.datetime({ offset: true }),
  last_at: z.iso.datetime({ offset: true }),
  messages: z.number().int().nonnegative(),
});
export type ChatThread = z.infer<typeof threadSchema>;

const messageSchema = z.object({
  id: z.uuid(),
  role: z.enum(["user", "assistant"]),
  text: z.string(),
  language: z.enum(["en", "hi", "ml"]).nullable(),
  created_at: z.iso.datetime({ offset: true }),
});
export type ChatMessage = z.infer<typeof messageSchema>;

/** The household's chats with FinBoy on the web and WhatsApp, newest first. */
export const listThreads = (signal?: AbortSignal) =>
  requestJson("/api/v1/assistant/threads", z.object({ threads: z.array(threadSchema) }), {
    signal,
  }).then((body) => body.threads);

export const getThread = (id: string, signal?: AbortSignal) =>
  requestJson(
    `/api/v1/assistant/threads/${encodeURIComponent(id)}`,
    z.object({ thread: threadSchema, messages: z.array(messageSchema) }),
    { signal },
  );

export async function deleteThread(id: string): Promise<void> {
  const response = await apiFetch(`/api/v1/assistant/threads/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw await failure(response);
}

export const deleteThreads = () =>
  requestJson("/api/v1/assistant/threads", z.object({ deleted: z.number().int() }), {
    method: "DELETE",
  });

/** Starter questions chosen from the household's own figures (no model call). */
export const getSuggestions = (signal?: AbortSignal) =>
  requestJson("/api/v1/assistant/suggestions", z.object({ suggestions: z.array(z.string()) }), {
    signal,
  }).then((body) => body.suggestions);

export const SPEECH_LIMITS = { characters: 600, bytes: 4 * 1024 * 1024 } as const;

export async function speechFor(
  answer: Pick<Answer, "speech_text" | "speech_language">,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await apiFetch("/api/v1/assistant/speak", {
    method: "POST",
    ...jsonBody({ text: answer.speech_text, language: answer.speech_language }),
    headers: { "Content-Type": "application/json", Accept: "audio/mpeg" },
    signal,
    timeoutMs: 60_000,
  });
  if (!response.ok) throw await failure(response);
  if (response.headers.get("content-type")?.split(";")[0] !== "audio/mpeg") {
    throw new ApiError("Speech returned an invalid recording.", response.status, {
      kind: "invalid_response",
    });
  }
  const data = await response.blob();
  if (!data.size || data.size > SPEECH_LIMITS.bytes) {
    throw new ApiError("Speech returned an invalid recording.", response.status, {
      kind: "invalid_response",
    });
  }
  return data;
}

export const RECORDING_LIMITS = { seconds: 30, bytes: 3 * 1024 * 1024 } as const;

export function transcribeAudio(audio: Blob, signal?: AbortSignal) {
  if (audio.size > RECORDING_LIMITS.bytes) {
    return Promise.reject(
      new ApiError("Recording must be at most 3 MB.", undefined, { kind: "validation" }),
    );
  }
  const body = new FormData();
  body.append("audio", audio, "question.webm");
  return requestJson(
    "/api/v1/assistant/transcribe",
    z.object({
      transcript: z.string().max(2000),
      detected_language: z.enum(["en", "hi", "ml", "unknown"]),
    }),
    { method: "POST", body, signal, timeoutMs: 60_000 },
  );
}
