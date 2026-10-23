import { z } from "zod";
import { requestJson } from "./http.ts";

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
const integer = z.number().int().safe();
export const transactionSchema = z.object({
  id: z.uuid(),
  direction: z.enum(["in", "out"]),
  kind: z.enum([
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
  ]),
  amount_minor: integer.positive(),
  currency: z.literal("INR"),
  merchant: z.string(),
  category: categorySchema,
  occurred_at: z.iso.datetime({ offset: true }),
  status: z.enum(["confirmed", "needs_review", "rejected", "merged", "failed"]),
  confidence: z.number().min(0).max(1),
  review_reason: z.string().nullable(),
  reference_id: z.string().nullable(),
  payment_instrument: z.string().nullable(),
  account_last4: z.string().nullable(),
  possible_duplicate_of_id: z.uuid().nullable(),
  linked_transaction_id: z.uuid().nullable(),
  merged_into_id: z.uuid().nullable(),
});
export const summarySchema = z.object({
  period_start: z.iso.date(),
  period_end: z.iso.date(),
  as_of: z.iso.date(),
  currency: z.literal("INR"),
  tracked_income_minor: integer,
  confirmed_outflows_minor: integer,
  upcoming_commitments_minor: integer,
  estimated_unallocated_minor: integer,
  pending_review_count: integer.nonnegative(),
  pending_review_minor: integer,
  income_transaction_count: integer.nonnegative(),
  outflow_transaction_count: integer.nonnegative(),
  commitment_count: integer.nonnegative(),
  categories: z.array(
    z.object({
      category: categorySchema,
      amount_minor: integer,
      currency: z.literal("INR"),
      transaction_count: integer.nonnegative(),
    }),
  ),
  evidence_transaction_ids: z.array(z.uuid()),
});
const commitmentSchema = z.object({
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
});
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
        "proposed_monthly",
      ]),
      amount_minor: integer,
      sign: z.enum(["+", "-"]),
    }),
  ),
  warnings: z.array(
    z.enum([
      "pending_review_items",
      "negative_remaining",
      "low_buffer",
      "incomplete_coverage",
    ]),
  ),
  disclaimer_key: z.literal("cash_flow_model_not_investment_advice"),
});
export type MoneySummary = z.infer<typeof summarySchema>;
export type Transaction = z.infer<typeof transactionSchema>;
export type Commitment = z.infer<typeof commitmentSchema>;
export type Simulation = z.infer<typeof simulationSchema>;
export const getSummary = (signal?: AbortSignal) =>
  requestJson("/api/v1/money/summary", summarySchema, { signal });
export const getCommitments = (signal?: AbortSignal) =>
  requestJson("/api/v1/money/commitments", z.array(commitmentSchema), {
    signal,
  });
export const simulate = (amount: number) =>
  requestJson("/api/v1/money/simulations", simulationSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      monthly_amount_minor: amount,
      label: "Monthly SIP",
    }),
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
export function label(value: string): string {
  if (value.startsWith("transaction:")) return "Matching record";
  const names: Record<string, string> = {
    food_dining: "Food & dining",
    loan_emi: "Loan EMI",
    amount_minor: "Amount",
    account_last4: "Account ending",
    user_locked_fields: "Fields you control",
  };
  return (
    names[value] ??
    value
      .replace(/_minor$/, "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}
export function inputPaise(value: string): number | null {
  if (!/^\d{1,10}(\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  const amount = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(amount) && amount > 0 ? amount : null;
}
