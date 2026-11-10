import { z } from "zod";
import { requestJson } from "./http.ts";

// Home's "For you": the coach's current nudges (docs/advisor-round/contract.md, phase 3).
export const nudgeKinds = [
  "weekly_recap",
  "due_soon",
  "budget_over",
  "unusual_payment",
  "income_in",
  "budget_near",
  "goal_progress",
  "new_regular",
] as const;
export type NudgeKind = (typeof nudgeKinds)[number];

const itemSchema = z.object({
  kind: z.enum(nudgeKinds),
  tone: z.enum(["warning", "good", "info"]),
  title: z.string().min(1).max(80),
  text: z.string().min(1).max(600),
  // A place in FinBoy only: an anchor on Home or an app path, never another site ("//host" too).
  href: z.string().regex(/^(#[a-z-]+|\/(?!\/)[A-Za-z0-9/?=&#_.-]*)$/),
  ask: z.string().min(1).max(500),
});
export type ForYouItem = z.infer<typeof itemSchema>;

const forYouSchema = z.object({
  items: z.array(itemSchema).max(3),
  // Whether the household's WhatsApp number gets these too ("none": no diary number linked).
  whatsapp: z.enum(["none", "off", "on"]),
});
export type ForYou = z.infer<typeof forYouSchema>;

export const getForYou = (signal?: AbortSignal) =>
  requestJson("/api/v1/coach", forYouSchema, { signal });

/** Ask FinBoy with the item's question already typed in, ready to send or change. */
export const askLink = (question: string) => `/assistant?ask=${encodeURIComponent(question)}`;
