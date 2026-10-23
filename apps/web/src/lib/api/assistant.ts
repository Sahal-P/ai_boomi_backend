import { z } from "zod";
import { apiBaseUrl, ApiError, requestJson } from "./http.ts";
import { simulationSchema, transactionSchema } from "./money.ts";

export const styles = [
  "auto",
  "en",
  "hi",
  "hinglish",
  "ml",
  "manglish",
] as const;
export type DisplayStyle = (typeof styles)[number];
export const answerSchema = z.object({
  intent: z.string(),
  policy: z.enum(["answer", "decline", "clarify"]),
  display_text: z.string(),
  speech_text: z.string(),
  speech_language: z.enum(["en", "hi", "ml"]),
  facts: z.array(
    z.object({
      key: z.string(),
      amount_minor: z.number().int().nullable(),
      count: z.number().int().nullable(),
      currency: z.literal("INR").nullable(),
    }),
  ),
  simulation: simulationSchema.nullable(),
  evidence_transactions: z.array(transactionSchema),
  warnings: z.array(z.string()),
});
export type Answer = z.infer<typeof answerSchema>;
export const askQuestion = (
  text: string,
  displayStyle: DisplayStyle,
  signal?: AbortSignal,
) =>
  requestJson("/api/v1/assistant/ask", answerSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, display_style: displayStyle }),
    signal,
    timeoutMs: 60_000,
  });
export async function speechFor(
  answer: Answer,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/assistant/speak`, {
    method: "POST",
    credentials: "omit",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: answer.speech_text,
      language: answer.speech_language,
    }),
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(60_000)])
      : AbortSignal.timeout(60_000),
  });
  if (
    !response.ok ||
    response.headers.get("content-type")?.split(";")[0] !== "audio/mpeg"
  )
    throw new ApiError(
      "Speech is unavailable. Your text answer is still here.",
      response.status,
    );
  const data = await response.blob();
  if (!data.size || data.size > 4 * 1024 * 1024)
    throw new ApiError("Speech returned an invalid recording.");
  return data;
}
export function transcribeAudio(audio: Blob, signal?: AbortSignal) {
  if (audio.size > 3 * 1024 * 1024)
    throw new ApiError("Recording must be at most 3 MB.");
  const body = new FormData();
  body.append("audio", audio, "question.webm");
  return requestJson(
    "/api/v1/assistant/transcribe",
    z.object({
      transcript: z.string(),
      detected_language: z.enum(["en", "hi", "ml", "unknown"]),
    }),
    { method: "POST", body, signal, timeoutMs: 60_000 },
  );
}
