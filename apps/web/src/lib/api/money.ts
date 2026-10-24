import { z } from "zod";
import { jsonBody, query, requestJson } from "./http.ts";

export const categories = [
  "salary",
  "other_income",
  "rent",
  "food_dining",
  "groceries",
  "transport",
  "shopping",
  "utilities",
  "subscriptions",
  "travel",
  "health",
  "education",
  "investments",
  "loan_emi",
  "fees",
  "transfer",
  "other",
] as const;
export const categorySchema = z.enum(categories);
export type Category = z.infer<typeof categorySchema>;

export const kinds = [
  "purchase",
  "salary",
  "income_other",
  "refund",
  "reversal",
  "fee",
  "bill_payment",
  "emi",
  "investment",
  "transfer",
] as const;
export const kindSchema = z.enum(kinds);
export type Kind = z.infer<typeof kindSchema>;

export const statuses = ["confirmed", "needs_review", "rejected", "merged", "failed"] as const;
export const statusSchema = z.enum(statuses);
export type RecordStatus = z.infer<typeof statusSchema>;

export const reviewReasons = [
  "low_confidence",
  "merchant_uncertain",
  "possible_duplicate",
  "category_uncertain",
  "unverified_payment",
] as const;
export type ReviewReason = (typeof reviewReasons)[number];
export const sourceModeSchema = z.enum(["gmail", "eml_upload", "demo_mailbox", "whatsapp_image"]);
export type SourceMode = z.infer<typeof sourceModeSchema>;
export const datasetSchema = z.enum(["household", "demo", "quarantined"]);
export type Dataset = z.infer<typeof datasetSchema>;

const integer = z.number().int().safe();
const count = integer.nonnegative();
const timestamp = z.iso.datetime({ offset: true });
export const opaque = z.string().min(1).max(200);
/** Contract windows are ISO dates; full timestamps are accepted without reinterpretation. */
export const dayOrTime = z.union([z.iso.date(), timestamp]);

/** Fields every transaction view has carried since phase 1 (assistant evidence uses these). */
export const baseTransactionSchema = z.object({
  id: z.uuid(),
  direction: z.enum(["in", "out"]),
  kind: kindSchema,
  amount_minor: integer.positive(),
  currency: z.literal("INR"),
  merchant: z.string(),
  category: categorySchema,
  occurred_at: timestamp,
  status: statusSchema,
  confidence: z.number().min(0).max(1),
  review_reason: z.enum(reviewReasons).nullable(),
  reference_id: z.string().nullable(),
  payment_instrument: z.string().nullable(),
  account_last4: z.string().nullable(),
  possible_duplicate_of_id: z.uuid().nullable(),
  linked_transaction_id: z.uuid().nullable(),
  merged_into_id: z.uuid().nullable(),
});
/** Contract v1 record: provenance, extraction quality and payment verification are separate facts. */
export const transactionSchema = baseTransactionSchema.extend({
  dataset: datasetSchema,
  source_modes: z.array(sourceModeSchema),
  source_count: count,
  extraction_quality: z.enum(["complete", "partial"]),
  payment_verification: z.enum(["verified", "unverified", "failed"]),
  version: opaque,
});
export type BaseTransaction = z.infer<typeof baseTransactionSchema>;
export type Transaction = z.infer<typeof transactionSchema>;

export const coverageSchema = z.object({
  sync_mode: z.literal("manual"),
  last_successful_scan_at: timestamp.nullable(),
  window_start: dayOrTime.nullable(),
  window_end: dayOrTime.nullable(),
  state: z.enum(["unknown", "partial", "scanned"]),
  truncated: z.boolean(),
  pending_review_count: count,
  failed_source_count: count,
  active_import_id: z.uuid().nullable(),
  quarantined_count: count,
});
export type Coverage = z.infer<typeof coverageSchema>;

const categoryTotalSchema = z.object({
  category: categorySchema,
  amount_minor: integer,
  currency: z.literal("INR"),
  transaction_count: count,
});
const summaryFields = {
  period_start: z.iso.date(),
  period_end: z.iso.date(),
  as_of: z.iso.date(),
  currency: z.literal("INR"),
  tracked_income_minor: integer,
  confirmed_outflows_minor: integer,
  upcoming_commitments_minor: integer,
  overdue_commitments_minor: integer,
  uncertain_commitments_minor: integer,
  unresolved_commitments_minor: integer,
  overdue_commitment_count: count,
  estimated_unallocated_minor: integer,
  pending_review_count: count,
  pending_review_minor: integer,
  income_transaction_count: count,
  outflow_transaction_count: count,
  commitment_count: count,
  categories: z.array(categoryTotalSchema),
  evidence_transaction_ids: z.array(z.uuid()),
  data_version: opaque,
};
/** Household summaries must never carry another dataset; a mismatch is rejected, not displayed. */
export const summarySchema = z.object({
  ...summaryFields,
  dataset: z.literal("household"),
  coverage: coverageSchema,
});
export const demoSummarySchema = z.object({
  ...summaryFields,
  dataset: z.literal("demo"),
  coverage: coverageSchema.optional(),
});
export type MoneySummary = z.infer<typeof summarySchema>;
export type DemoSummary = z.infer<typeof demoSummarySchema>;

export const commitmentSchema = z.object({
  id: z.uuid(),
  kind: z.enum(["bill", "emi", "subscription", "sip"]),
  label: z.string(),
  amount_minor: integer,
  currency: z.literal("INR"),
  due_date: z.iso.date(),
  status: z.enum(["upcoming", "paid", "dismissed"]),
  confidence: z.number().min(0).max(1),
  source_event_id: z.uuid().nullable(),
  paid_transaction_id: z.uuid().nullable(),
  version: opaque,
  dataset: datasetSchema,
  liability_state: z.enum(["upcoming", "overdue", "paid", "dismissed"]),
  uncertain: z.boolean(),
});
export type Commitment = z.infer<typeof commitmentSchema>;

export const transactionSourceSchema = z.object({
  id: z.uuid(),
  email_source_id: z.uuid(),
  source: sourceModeSchema,
  sender_domain: z.string(),
  received_at: timestamp,
  classification: z.string(),
  event_type: z.string(),
  amount_minor: z.number().int(),
  currency: z.literal("INR"),
  merchant: z.string().nullable(),
  occurred_at: timestamp.nullable(),
  due_date: z.iso.date().nullable(),
  extraction_method: z.enum(["rule", "llm"]),
  extractor_id: z.string(),
  evidence: z.record(z.string(), z.string().max(80)),
  field_confidence: z.record(z.string(), z.number()),
});
export type TransactionSource = z.infer<typeof transactionSourceSchema>;

const obligationListSchema = z.object({ items: z.array(commitmentSchema), data_version: opaque });
export const obligationDetailSchema = z.object({
  commitment: commitmentSchema,
  sources: z.array(transactionSourceSchema),
  version: opaque,
});
export type ObligationDetail = z.infer<typeof obligationDetailSchema>;
export type ObligationChange = {
  expected_version: string;
  label?: string;
  amount_minor?: number;
  due_date?: string;
  status?: "upcoming" | "paid" | "dismissed";
  paid_transaction_id?: string | null;
};

export const simulationSchema = z.object({
  summary: summarySchema,
  proposed_monthly_minor: integer.positive(),
  remaining_after_proposal_minor: integer,
  lines: z.array(
    z.object({
      label_key: z.enum([
        "tracked_income",
        "confirmed_outflows",
        "upcoming_commitments",
        "overdue_commitments",
        "proposed_monthly",
      ]),
      amount_minor: integer,
      sign: z.enum(["+", "-"]),
    }),
  ),
  warnings: z.array(
    z.enum(["pending_review_items", "negative_remaining", "low_buffer", "incomplete_coverage"]),
  ),
  disclaimer_key: z.literal("cash_flow_model_not_investment_advice"),
});
export type Simulation = z.infer<typeof simulationSchema>;

/** A month the user selected; `null` means the current IST month resolved by the backend. */
export type Period = { year: number; month: number } | null;

export function periodQuery(period: Period) {
  return period
    ? { period: "month", year: period.year, month: period.month }
    : { period: "current_month" };
}

export const getSummary = (period: Period, signal?: AbortSignal) =>
  requestJson(`/api/v1/money/summary${query(periodQuery(period))}`, summarySchema, { signal });
export const getObligations = (
  status: "unresolved" | "all" | "paid" | "dismissed",
  signal?: AbortSignal,
) =>
  requestJson(`/api/v1/money/obligations${query({ status })}`, obligationListSchema, { signal });
export const getObligation = (id: string, signal?: AbortSignal) =>
  requestJson(`/api/v1/money/obligations/${encodeURIComponent(id)}`, obligationDetailSchema, {
    signal,
  });
export const updateObligation = (id: string, change: ObligationChange) =>
  requestJson(`/api/v1/money/obligations/${encodeURIComponent(id)}`, obligationDetailSchema, {
    method: "PATCH",
    ...jsonBody(change),
  });
export const simulate = (amount: number, signal?: AbortSignal) =>
  requestJson("/api/v1/money/simulations", simulationSchema, {
    method: "POST",
    ...jsonBody({ monthly_amount_minor: amount, label: "Monthly SIP", include_overdue_line: true }),
    signal,
    timeoutMs: 15_000,
  });

export const recordsNote =
  "Based on email-derived and confirmed records. Your actual bank balance may differ.";
export const simulationDisclaimer =
  "This models cash flow from FinBoy's tracked records. It is not a recommendation to purchase any security.";

export const formatMoney = (minor: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: minor % 100 ? 2 : 0,
  }).format(minor / 100);

/** Rupee input to integer paise; display conversion only, never arithmetic on totals. */
export function inputPaise(value: string): number | null {
  const trimmed = value.trim().replaceAll(",", "");
  if (!/^\d{1,10}(\.\d{1,2})?$/.test(trimmed)) return null;
  const [whole, fraction = ""] = trimmed.split(".");
  const amount = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(amount) && amount > 0 ? amount : null;
}

export function rupeeInput(minor: number): string {
  return (minor / 100).toFixed(minor % 100 ? 2 : 0);
}
