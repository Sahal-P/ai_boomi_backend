import { z } from "zod";
import { apiFetch, failure, jsonBody, requestJson } from "./http.ts";

// Feedback to the FinBoy team (docs/feedback-round/contract.md): a problem, an idea or something
// else, the screen it came from and at most one screenshot, redrawn in the browser before it goes.
export const feedbackKinds = ["problem", "idea", "other"] as const;
export type FeedbackKind = (typeof feedbackKinds)[number];
export const feedbackStatuses = ["new", "planned", "done"] as const;
export type FeedbackStatus = (typeof feedbackStatuses)[number];
export const screenshotTypes = ["image/webp", "image/jpeg", "image/png"] as const;
export type ScreenshotType = (typeof screenshotTypes)[number];

export const FEEDBACK_MESSAGE_LIMIT = 2000;
export const FEEDBACK_PAGE_LIMIT = 200;
/** The API's limit on one screenshot's bytes. */
export const SCREENSHOT_LIMIT = 1_500_000;

const instant = z.iso.datetime({ offset: true });
const itemSchema = z.object({
  id: z.uuid(),
  kind: z.enum(feedbackKinds),
  message: z.string().min(1).max(FEEDBACK_MESSAGE_LIMIT),
  page: z.string().max(FEEDBACK_PAGE_LIMIT),
  status: z.enum(feedbackStatuses),
  has_screenshot: z.boolean(),
  created_at: instant,
  status_changed_at: instant.nullable(),
});
export type FeedbackItem = z.infer<typeof itemSchema>;

const listSchema = z.object({ screenshots: z.boolean(), items: z.array(itemSchema).max(50) });
export type FeedbackList = z.infer<typeof listSchema>;
const sentSchema = z.object({ item: itemSchema, screenshot_saved: z.boolean() });
export type FeedbackSent = z.infer<typeof sentSchema>;

/** A redrawn screenshot: its type and its bytes as base64, without a data: prefix. */
export type Screenshot = { type: ScreenshotType; data: string };
export type FeedbackDraft = {
  kind: FeedbackKind;
  message: string;
  page: string;
  screenshot: Screenshot | null;
};

/** The app screen feedback came from: a path only, never a query, a fragment or another site. */
export function screenFrom(value: string | null | undefined): string {
  if (!value || value.length > 512 || !value.startsWith("/") || /^\/[\\/]/.test(value)) return "";
  try {
    const base = "https://finboy.invalid";
    const url = new URL(value, base);
    if (url.origin !== base || url.pathname === "/feedback") return "";
    return url.pathname.slice(0, FEEDBACK_PAGE_LIMIT);
  } catch {
    return "";
  }
}

export const listFeedback = (signal?: AbortSignal) =>
  requestJson("/api/v1/feedback", listSchema, { signal });

export const sendFeedback = (draft: FeedbackDraft) =>
  requestJson("/api/v1/feedback", sentSchema, {
    method: "POST",
    // A screenshot is up to 2 MB of text; slow phone connections need longer than a click.
    timeoutMs: draft.screenshot ? 60_000 : 15_000,
    ...jsonBody({
      kind: draft.kind,
      message: draft.message.trim(),
      page: screenFrom(draft.page),
      ...(draft.screenshot ? { screenshot: draft.screenshot } : {}),
    }),
  });

export async function deleteFeedback(id: string): Promise<void> {
  const response = await apiFetch(`/api/v1/feedback/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!response.ok) throw await failure(response);
}
