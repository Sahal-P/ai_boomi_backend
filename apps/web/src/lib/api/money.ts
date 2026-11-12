import { z } from "zod";
import type { Month } from "../dates.ts";
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
  "farming",
  "livestock",
  "phone_recharge",
  "family_events",
  "remittance",
  "wages",
  "farm_sales",
  "govt_benefit",
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
export const sourceModeSchema = z.enum([
  "gmail",
  "eml_upload",
  "demo_mailbox",
  "whatsapp_image",
  "whatsapp_voice",
  "manual_entry",
  "gpay_statement",
]);
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
  kind: z.enum(["bill", "emi", "subscription", "sip", "loan"]),
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

/** A chosen month; a range of whole months (Reports, an imported statement); `null` is this month. */
export type MonthRange = { from: Month; to: Month };
export type Period = Month | MonthRange | null;
export const isRange = (period: Period): period is MonthRange => period !== null && "from" in period;
/** The API reads at most two years at once. */
export const MAX_RANGE_MONTHS = 24;

const monthIndex = (month: Month) => month.year * 12 + month.month - 1;
const pad = (value: number) => String(value).padStart(2, "0");
const validMonth = (year: number, month: number) =>
  Number.isInteger(year) && year >= 2000 && year <= 2100 && Number.isInteger(month) && month >= 1 && month <= 12;

function monthParam(value: string | null): Month | null {
  const match = /^(\d{4})-(\d{2})$/.exec(value ?? "");
  const year = Number(match?.[1]);
  const month = Number(match?.[2]);
  return match && validMonth(year, month) ? { year, month } : null;
}

/** `YYYY-MM`, as ranges travel in links. */
export const monthKey = (month: Month) => `${month.year}-${pad(month.month)}`;

/** Every month of a range, oldest first. */
export function rangeMonths(range: MonthRange): Month[] {
  const first = monthIndex(range.from);
  return Array.from({ length: monthIndex(range.to) - first + 1 }, (_, offset) => ({
    year: Math.floor((first + offset) / 12),
    month: ((first + offset) % 12) + 1,
  }));
}

/** The month in a URL (`?year=&month=`), or null for the current month. Home reads only this. */
export function monthFromParams(params: URLSearchParams): Month | null {
  const year = Number(params.get("year"));
  const month = Number(params.get("month"));
  return validMonth(year, month) ? { year, month } : null;
}

/** A range (`?from=2026-04&to=2026-09`) or a month in a screen's URL; null for the current month. */
export function periodFromParams(params: URLSearchParams): Period {
  const from = monthParam(params.get("from"));
  const to = monthParam(params.get("to"));
  if (from && to && monthIndex(from) <= monthIndex(to) && monthIndex(to) - monthIndex(from) < MAX_RANGE_MONTHS) {
    return monthIndex(from) === monthIndex(to) ? from : { from, to };
  }
  return monthFromParams(params);
}

/** `&year=…&month=…` or `&from=…&to=…` to carry the period into a link; empty for this month. */
export function periodSearch(period: Period): string {
  if (isRange(period)) return `&from=${monthKey(period.from)}&to=${monthKey(period.to)}`;
  return period ? `&year=${period.year}&month=${period.month}` : "";
}

export function periodQuery(period: Period) {
  if (isRange(period)) {
    const last = new Date(Date.UTC(period.to.year, period.to.month, 0)).getUTCDate();
    return {
      period: "range",
      start: `${monthKey(period.from)}-01`,
      end: `${monthKey(period.to)}-${pad(last)}`,
    };
  }
  return period
    ? { period: "month", year: period.year, month: period.month }
    : { period: "current_month" };
}

export const getSummary = (period: Period, signal?: AbortSignal) =>
  requestJson(`/api/v1/money/summary${query(periodQuery(period))}`, summarySchema, { signal });
const payeeTotalSchema = z.object({
  name: z.string(),
  amount_minor: count,
  count: count,
  share: z.number().min(0).max(1),
  category: categorySchema,
});
export type PayeeTotal = z.infer<typeof payeeTotalSchema>;
export const insightsSchema = z.object({
  period_start: z.iso.date(),
  period_end: z.iso.date(),
  months: count,
  money_out_minor: count,
  money_in_minor: count,
  payment_count: count,
  top_payees: z.array(payeeTotalSchema),
  top_senders: z.array(payeeTotalSchema),
  biggest: z.array(
    z.object({ id: z.uuid(), name: z.string(), amount_minor: count, occurred_at: timestamp, category: categorySchema }),
  ),
  regular: z.array(
    z.object({
      name: z.string(),
      usual_minor: count,
      months: count,
      last_paid: z.iso.date(),
      next_expected: z.iso.date(),
      category: categorySchema,
    }),
  ),
  regular_monthly_minor: count,
  people: z.array(
    z.object({
      name: z.string(),
      sent_minor: count,
      received_minor: count,
      balance_minor: integer,
      count: count,
      last_on: z.iso.date(),
    }),
  ),
  small: z.object({
    threshold_minor: count,
    count: count,
    amount_minor: count,
    per_month_minor: count,
    count_share: z.number().min(0).max(1),
    amount_share: z.number().min(0).max(1),
    places: z.array(payeeTotalSchema),
  }),
  data_version: opaque,
});
export type Insights = z.infer<typeof insightsSchema>;
export const getInsights = (period: Period, signal?: AbortSignal) =>
  requestJson(`/api/v1/money/insights${query(periodQuery(period))}`, insightsSchema, { signal });

const payeeListSchema = z.object({
  items: z.array(z.object({ name: z.string(), count: count, amount_minor: count })),
  spent_minor: count,
  unsorted_minor: count,
  data_version: opaque,
});
export type PayeeList = z.infer<typeof payeeListSchema>;
/** Spending payees still under "Other" in the period, largest first. */
export const getPayees = (period: Period, signal?: AbortSignal) =>
  requestJson(`/api/v1/money/payees${query(periodQuery(period))}`, payeeListSchema, { signal });
/** One category for every spending record of the payee, remembered for its next entries. */
export const sortPayee = (name: string, category: Category, expectedVersion: string) =>
  requestJson(
    "/api/v1/money/payees/category",
    z.object({ updated: count, data_version: opaque }),
    { method: "POST", ...jsonBody({ name, category, expected_version: expectedVersion }) },
  );
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
