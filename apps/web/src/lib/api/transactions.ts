import { z } from "zod";
import { requestJson } from "./http.ts";
import { categorySchema, transactionSchema } from "./money.ts";

export const detailSchema = z.object({
  transaction: transactionSchema,
  sources: z.array(
    z.object({
      id: z.uuid(),
      email_source_id: z.uuid(),
      source: z.enum(["gmail", "eml_upload", "demo_mailbox"]),
      sender_domain: z.string(),
      received_at: z.iso.datetime({ offset: true }),
      classification: z.string(),
      event_type: z.string(),
      amount_minor: z.number().int(),
      currency: z.literal("INR"),
      merchant: z.string().nullable(),
      occurred_at: z.iso.datetime({ offset: true }).nullable(),
      due_date: z.iso.date().nullable(),
      extraction_method: z.enum(["rule", "llm"]),
      extractor_id: z.string(),
      evidence: z.record(z.string(), z.string().max(80)),
      field_confidence: z.record(z.string(), z.number()),
    }),
  ),
  confidence_factors: z.record(z.string(), z.number().nullable()),
  revisions: z.array(
    z.object({
      id: z.uuid(),
      field: z.string(),
      old_value: z.json(),
      new_value: z.json(),
      changed_by: z.enum(["user", "system"]),
      reason: z.string(),
      changed_at: z.iso.datetime({ offset: true }),
    }),
  ),
});
export type TransactionDetail = z.infer<typeof detailSchema>;
export type Correction = {
  category?: z.infer<typeof categorySchema>;
  merchant?: string;
  amount_minor?: number;
};
export const getTransactions = (query = "", signal?: AbortSignal) =>
  requestJson(
    `/api/v1/transactions${query ? `?${query}` : ""}`,
    z.array(transactionSchema),
    { signal },
  );
export const getTransaction = (id: string, signal?: AbortSignal) =>
  requestJson(`/api/v1/transactions/${encodeURIComponent(id)}`, detailSchema, {
    signal,
  });
export const correctTransaction = (id: string, body: Correction) =>
  requestJson(`/api/v1/transactions/${encodeURIComponent(id)}`, detailSchema, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const reviewTransaction = (
  id: string,
  action: "confirm" | "reject" | "merge" | "keep-separate",
  keepId?: string,
) =>
  requestJson(
    `/api/v1/transactions/${encodeURIComponent(id)}/${action}`,
    detailSchema,
    {
      method: "POST",
      ...(keepId
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ keep_id: keepId }),
          }
        : {}),
    },
  );
