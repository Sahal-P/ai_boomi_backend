import { z } from "zod";
import { jsonBody, requestJson } from "./http.ts";
import { categorySchema } from "./money.ts";

const day = z.iso.date();

export const entryPreviewSchema = z.object({
  kind: z.enum(["spent", "received", "due", "question", "unclear"]),
  amount_minor: z.number().int().positive().nullable(),
  counterparty: z.string().max(80).nullable(),
  category: categorySchema,
  day: day.nullable(),
  due_date: day.nullable(),
  label: z.string().max(80).nullable(),
});
export type EntryPreview = z.infer<typeof entryPreviewSchema>;

export type EntryFields = {
  kind: "spent" | "received" | "due";
  amount_minor: number;
  counterparty: string | null;
  category: EntryPreview["category"];
  day: string | null;
  due_date: string | null;
  label: string | null;
};

export const entrySavedSchema = z.object({
  kind: z.enum(["record", "due"]),
  transaction_id: z.uuid().nullable(),
  decision_id: z.uuid().nullable(),
  obligation_id: z.uuid().nullable(),
  data_version: z.string().min(1),
});
export type EntrySaved = z.infer<typeof entrySavedSchema>;

/** Reads one sentence; nothing is stored until Save. */
export const previewEntry = (text: string, signal?: AbortSignal) =>
  requestJson("/api/v1/entries/preview", entryPreviewSchema, {
    method: "POST",
    signal,
    timeoutMs: 20_000,
    ...jsonBody({ text }),
  });

/** Save is the confirmation: the server checks every field again. */
export const saveEntry = (fields: EntryFields) =>
  requestJson("/api/v1/entries", entrySavedSchema, {
    method: "POST",
    timeoutMs: 20_000,
    ...jsonBody(
      fields.kind === "due"
        ? {
            kind: "due",
            amount_minor: fields.amount_minor,
            label: fields.label ?? fields.counterparty,
            category: fields.category,
            due_date: fields.due_date,
          }
        : {
            kind: fields.kind,
            amount_minor: fields.amount_minor,
            counterparty: fields.counterparty,
            category: fields.category,
            day: fields.day,
          },
    ),
  });
