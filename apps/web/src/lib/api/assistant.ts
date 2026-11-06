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
});
export type Answer = z.infer<typeof answerSchema>;
export type MemoryChange = Answer["memory_changes"][number];
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
