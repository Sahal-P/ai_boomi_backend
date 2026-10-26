import type {
  Category,
  Commitment,
  Dataset,
  Kind,
  RecordStatus,
  ReviewReason,
  Simulation,
  SourceMode,
  Transaction,
} from "@/lib/api/money";
import type { ImportIssue } from "@/lib/api/imports";

// Human copy for fixed backend values. Unknown values get neutral copy, never title-cased keys.

export const categoryLabels: Record<Category, string> = {
  salary: "Salary",
  other_income: "Other income",
  rent: "Rent",
  food_dining: "Food & dining",
  groceries: "Groceries",
  transport: "Transport",
  shopping: "Shopping",
  utilities: "Utilities",
  subscriptions: "Subscriptions",
  travel: "Travel",
  health: "Health",
  education: "Education",
  investments: "Investments",
  loan_emi: "Loan EMI",
  fees: "Fees",
  transfer: "Transfer",
  farming: "Farming",
  livestock: "Livestock",
  phone_recharge: "Phone recharge",
  family_events: "Weddings & festivals",
  remittance: "Family money",
  wages: "Wages",
  farm_sales: "Farm sales",
  govt_benefit: "Government payments",
  other: "Other",
};

export const kindLabels: Record<Kind, string> = {
  purchase: "Purchase",
  salary: "Salary",
  income_other: "Other income",
  refund: "Refund",
  reversal: "Reversal",
  fee: "Fee",
  bill_payment: "Bill payment",
  emi: "EMI",
  investment: "Investment",
  transfer: "Transfer",
};

export const statusLabels: Record<RecordStatus, string> = {
  confirmed: "Confirmed",
  needs_review: "Needs review",
  rejected: "Rejected",
  merged: "Merged duplicate",
  failed: "Failed payment",
};

export const sourceLabels: Record<SourceMode, string> = {
  gmail: "Gmail",
  eml_upload: "Uploaded email",
  demo_mailbox: "Sample mailbox",
  whatsapp_image: "WhatsApp screenshot",
  whatsapp_voice: "WhatsApp voice note",
};

const ownMessages: Partial<Record<SourceMode, string>> = {
  whatsapp_image: "Your WhatsApp screenshot",
  whatsapp_voice: "Your WhatsApp voice note",
};

/** WhatsApp sources carry a placeholder sender domain; name the household's own message instead. */
export function sourceSender(source: { source: SourceMode; sender_domain: string }): string {
  return ownMessages[source.source] ?? source.sender_domain;
}

export const datasetLabels: Record<Dataset, string> = {
  household: "Household",
  demo: "Sample data",
  quarantined: "On hold",
};

export const reviewReasons: Record<
  ReviewReason,
  { title: string; detail: string; resolve: string }
> = {
  unverified_payment: {
    title: "Payment not verified",
    detail: "An order or invoice email doesn't prove that money left your account.",
    resolve:
      "Confirm only if you know it was paid — for example, a bank alert or statement shows it.",
  },
  merchant_uncertain: {
    title: "Merchant unclear",
    detail: "FinBoy couldn't read a clear merchant name from the email.",
    resolve: "Correct the merchant name, then save and confirm.",
  },
  possible_duplicate: {
    title: "Possible duplicate",
    detail: "Another record looks like the same payment.",
    resolve: "Compare the two side by side, then merge them or keep both.",
  },
  category_uncertain: {
    title: "Category unclear",
    detail: "FinBoy couldn't tell what kind of spending this is.",
    resolve: "Choose a category, then save and confirm.",
  },
  low_confidence: {
    title: "Details need checking",
    detail: "Some details were read with low certainty.",
    resolve: "Check the amount, date and merchant against the evidence, then confirm.",
  },
};

export const paymentLabels: Record<Transaction["payment_verification"], string> = {
  verified: "Payment confirmed by a bank or card email",
  unverified: "Payment not verified",
  failed: "Payment attempt failed",
};

export const extractionLabels: Record<Transaction["extraction_quality"], string> = {
  complete: "All key details found in the email",
  partial: "Some details were missing from the email",
};

const screenshotExtractionLabels: Record<Transaction["extraction_quality"], string> = {
  complete: "All key details found in the screenshot",
  partial: "Some details were missing from the screenshot",
};

const voiceExtractionLabels: Record<Transaction["extraction_quality"], string> = {
  complete: "All key details heard in your voice note",
  partial: "Some details were unclear in your voice note",
};

function onlyFrom(row: { source_modes?: readonly SourceMode[] }, mode: SourceMode): boolean {
  return Boolean(row.source_modes?.length) && Boolean(row.source_modes?.every((item) => item === mode));
}

/** Records evidenced only by WhatsApp screenshots; email wording would misdescribe them. */
export function screenshotOnly(row: { source_modes?: readonly SourceMode[] }): boolean {
  return onlyFrom(row, "whatsapp_image");
}

/** Records the household told FinBoy about in a WhatsApp voice note or message. */
export function voiceOnly(row: { source_modes?: readonly SourceMode[] }): boolean {
  return onlyFrom(row, "whatsapp_voice");
}

export function extractionLabel(row: Pick<Transaction, "extraction_quality" | "source_modes">): string {
  const labels = screenshotOnly(row) ? screenshotExtractionLabels : voiceOnly(row) ? voiceExtractionLabels : extractionLabels;
  return labels[row.extraction_quality];
}

/** A screenshot or voice note never proves settlement; a confirmed one was confirmed by the household. */
export function paymentLabel(row: Pick<Transaction, "payment_verification" | "source_modes">): string {
  if (row.payment_verification === "verified" && screenshotOnly(row)) return "Confirmed by you from a payment screenshot";
  if (row.payment_verification === "verified" && voiceOnly(row)) return "Confirmed by you from a voice note";
  return paymentLabels[row.payment_verification];
}

const screenshotReasonDetails: Partial<Record<ReviewReason, string>> = {
  unverified_payment: "A payment screenshot shows what an app displayed; it doesn't prove that money left your account.",
  merchant_uncertain: "FinBoy couldn't read a clear payee name from the screenshot.",
};

const voiceReasonDetails: Partial<Record<ReviewReason, string>> = {
  unverified_payment: "A voice note records what you told FinBoy; it doesn't prove that money moved.",
  merchant_uncertain: "FinBoy couldn't hear a clear name in your voice note.",
};

export const obligationKindLabels: Record<Commitment["kind"], string> = {
  bill: "Bill",
  emi: "EMI",
  subscription: "Subscription",
  sip: "SIP",
  loan: "Loan",
};

export const liabilityLabels: Record<Commitment["liability_state"], string> = {
  upcoming: "Due",
  overdue: "Overdue",
  paid: "Paid",
  dismissed: "Dismissed",
};

export const simulationLineLabels: Record<Simulation["lines"][number]["label_key"], string> = {
  tracked_income: "Tracked income",
  confirmed_outflows: "Confirmed net outflows",
  upcoming_commitments: "Upcoming obligations",
  overdue_commitments: "Overdue obligations",
  proposed_monthly: "Monthly amount set aside",
};

export const simulationWarningLabels: Record<Simulation["warnings"][number], string> = {
  pending_review_items: "Records waiting for review aren't included in this estimate.",
  negative_remaining: "This would leave less than nothing in your tracked records.",
  low_buffer: "This leaves only a thin buffer in your tracked records.",
  incomplete_coverage: "Email coverage is incomplete, so some spending may be missing.",
};

export const issueReasonLabels: Record<ImportIssue["reason"], string> = {
  extraction_failed: "Couldn't read the payment details",
  no_supported_events: "No supported payment found in the email",
  message_unavailable: "The email is no longer available",
};

export const confidenceFactorLabels: Record<string, string> = {
  trusted_sender_template: "Recognised sender format",
  deterministic_amount_date: "Amount and date read exactly",
  unique_reference: "Unique payment reference",
  cross_source_agreement: "Other emails agree",
  merchant_category_quality: "Clear merchant and category",
  source_count: "Supporting emails",
};

const evidenceFieldLabels: Record<string, string> = {
  amount_minor: "Amount",
  amount: "Amount",
  merchant: "Merchant",
  occurred_at: "Date",
  date: "Date",
  due_date: "Due date",
  reference_id: "Reference",
  account_last4: "Account ending",
  payment_instrument: "Paid with",
  status: "Status",
  subject: "Subject",
};

export function evidenceFieldLabel(key: string): string {
  return evidenceFieldLabels[key] ?? "Other detail";
}

export const auditEventLabels: Record<string, string> = {
  "gmail.connected": "Gmail connected",
  "gmail.sync_requested": "Scan requested",
  "gmail.paused": "Scans paused",
  "gmail.resumed": "Scans allowed again",
  "gmail.revoked": "Gmail access revoked",
  "gmail.revoke_failed": "Gmail disconnect couldn't finish",
  "gmail.reconnect_required": "Gmail needs reconnecting",
  "import.started": "Import started",
  "import.completed": "Import finished",
  "import.failed": "Import stopped",
  "data.deleted": "Imported data deleted",
  "transaction.corrected": "Record corrected",
  "transaction.merged": "Duplicate merged",
};

export function reasonFor(
  row: Pick<Transaction, "review_reason" | "status"> & { source_modes?: readonly SourceMode[] },
) {
  if (row.status !== "needs_review" || !row.review_reason) return null;
  const reason = reviewReasons[row.review_reason];
  const detail = screenshotOnly(row)
    ? screenshotReasonDetails[row.review_reason]
    : voiceOnly(row)
      ? voiceReasonDetails[row.review_reason]
      : undefined;
  return detail ? { ...reason, detail } : reason;
}

/** How a record affects the overview, so list rows can be reconciled without opening each one. */
export function effectLabel(row: Pick<Transaction, "status" | "kind" | "direction">): string {
  if (row.status === "needs_review") return "Not counted until reviewed";
  if (row.status === "rejected") return "Not counted (rejected)";
  if (row.status === "merged") return "Counted once, in the record it was merged into";
  if (row.status === "failed") return "Not counted (payment failed)";
  if (row.kind === "transfer") return "Transfer — not counted as spending";
  if (row.kind === "refund" || row.kind === "reversal") return "Reduces spending";
  if (row.direction === "in") {
    return row.kind === "salary" || row.kind === "income_other"
      ? "Counted as income"
      : "Not counted as income";
  }
  return "Counted as spending";
}
