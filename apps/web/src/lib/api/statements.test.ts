import assert from "node:assert/strict";
import { test } from "node:test";
import { rangeLabel } from "../dates.ts";
import { extractionLabel, paymentLabel } from "../labels.ts";
import { sessionSchema } from "./auth.ts";
import { importRunSchema, statementFileProblem } from "./imports.ts";
import {
  insightsSchema,
  monthFromParams,
  periodFromParams,
  periodQuery,
  periodSearch,
  rangeMonths,
  type Transaction,
} from "./money.ts";

const params = (value: string) => new URLSearchParams(value);

test("a statement's months travel as a range; anything else falls back to a month or this month", () => {
  assert.deepEqual(periodFromParams(params("from=2026-04&to=2026-09")), {
    from: { year: 2026, month: 4 },
    to: { year: 2026, month: 9 },
  });
  assert.deepEqual(periodFromParams(params("from=2026-04&to=2026-04")), { year: 2026, month: 4 });
  assert.equal(periodFromParams(params("from=2026-09&to=2026-04")), null);
  assert.equal(periodFromParams(params("from=2024-01&to=2026-01")), null, "longer than two years");
  assert.deepEqual(periodFromParams(params("from=2026-13&to=2026-14&year=2026&month=3")), { year: 2026, month: 3 });
  assert.equal(monthFromParams(params("from=2026-04&to=2026-09")), null, "Home reads months only");
});

test("ranges become links and API queries covering whole months", () => {
  const range = { from: { year: 2025, month: 11 }, to: { year: 2026, month: 2 } };
  assert.equal(periodSearch(range), "&from=2025-11&to=2026-02");
  assert.equal(periodSearch({ year: 2026, month: 4 }), "&year=2026&month=4");
  assert.equal(periodSearch(null), "");
  assert.deepEqual(periodQuery(range), { period: "range", start: "2025-11-01", end: "2026-02-28" });
  assert.deepEqual(periodQuery({ from: { year: 2028, month: 2 }, to: { year: 2028, month: 2 } }), {
    period: "range",
    start: "2028-02-01",
    end: "2028-02-29",
  });
  assert.deepEqual(
    rangeMonths(range).map((month) => `${month.year}-${month.month}`),
    ["2025-11", "2025-12", "2026-1", "2026-2"],
  );
  assert.equal(rangeLabel({ year: 2026, month: 4 }, { year: 2026, month: 6 }), "Apr – Jun 2026");
  assert.equal(rangeLabel({ year: 2025, month: 11 }, { year: 2026, month: 4 }), "Nov 2025 – Apr 2026");
});

test("only a PDF up to 10 MB is sent", () => {
  assert.equal(statementFileProblem({ name: "gpay_statement.PDF", size: 1_099_406, type: "application/pdf" }), null);
  assert.equal(statementFileProblem({ name: "statement.pdf", size: 10, type: "" }), null);
  assert.equal(statementFileProblem({ name: "statement.png", size: 10, type: "image/png" }), "not_pdf");
  assert.equal(statementFileProblem({ name: "statement.pdf", size: 10, type: "text/html" }), "not_pdf");
  assert.equal(statementFileProblem({ name: "statement.pdf", size: 0, type: "application/pdf" }), "empty");
  assert.equal(statementFileProblem({ name: "statement.pdf", size: 10 * 1024 * 1024 + 1, type: "application/pdf" }), "too_large");
});

const run = {
  id: "30000000-0000-4000-8000-000000000001",
  mode: "gpay_statement",
  status: "completed",
  headers_checked: 240,
  candidates_found: 240,
  emails_processed: 240,
  events_extracted: 240,
  transactions_created: 228,
  duplicates_merged: 9,
  needs_review: 0,
  non_financial_skipped: 0,
  failed: 0,
  error_code: null,
  started_at: "2026-10-31T20:40:00+05:30",
  finished_at: "2026-10-31T20:40:02+05:30",
  outcome: "complete",
  retryable: false,
  retry_strategy: "none",
  cancel_requested: false,
  window_start: "2026-04-01",
  window_end: "2026-09-30",
  truncated: false,
  data_version: "42",
  can_continue: false,
};

test("an import may carry a statement summary; older servers' runs still parse", () => {
  const statement = {
    provider: "gpay",
    period_start: "2026-04-01",
    period_end: "2026-09-30",
    pages: 27,
    rows: 240,
    new: 228,
    linked: 9,
    possible_duplicates: 0,
    already_imported: 0,
    not_counted: 0,
    sent_minor: 18250075,
    received_minor: 9640000,
    paid_minor: 18250075,
    got_minor: 9640000,
    reconciled: true,
    accounts: ["Sample Bank ••1234"],
    holder_matches: null,
    removed_at: null,
  };
  assert.equal(importRunSchema.parse({ ...run, statement }).statement?.rows, 240);
  assert.equal(importRunSchema.parse(run).statement, null);
  assert.equal(importRunSchema.safeParse({ ...run, statement: { ...statement, provider: "phonepe" } }).success, false);
});

test("the session says whether statements can be imported, off when an older server is silent", () => {
  const view = {
    authenticated: true,
    required: false,
    household: null,
    sign_in: { whatsapp: false, whatsapp_number: null, google_client_id: null, password: false, signup_open: false, gmail: true },
  };
  assert.equal(sessionSchema.parse(view).statement_import, false);
  assert.equal(sessionSchema.parse({ ...view, statement_import: true }).statement_import, true);
});

test("insights parse with every section, including negative balances with people", () => {
  const payee = { name: "Asha Stores", amount_minor: 31500, count: 3, share: 0.2, category: "groceries" };
  const parsed = insightsSchema.parse({
    period_start: "2026-04-01",
    period_end: "2026-09-30",
    months: 6,
    money_out_minor: 18250075,
    money_in_minor: 9640000,
    payment_count: 214,
    top_payees: [payee],
    top_senders: [],
    biggest: [{ id: "30000000-0000-4000-8000-000000000002", name: "Asha Stores", amount_minor: 31500, occurred_at: "2026-04-01T10:42:00+05:30", category: "groceries" }],
    regular: [{ name: "Sample Broadband", usual_minor: 74950, months: 4, last_paid: "2026-09-05", next_expected: "2026-10-05", category: "utilities" }],
    regular_monthly_minor: 74950,
    people: [{ name: "Ravi Kumar", sent_minor: 1240000, received_minor: 1232000, balance_minor: -8000, count: 2, last_on: "2026-05-09" }],
    small: { threshold_minor: 20000, count: 96, amount_minor: 812400, per_month_minor: 135400, count_share: 0.45, amount_share: 0.045, places: [payee] },
    data_version: "42",
  });
  assert.equal(parsed.people[0]?.balance_minor, -8000);
});

test("a record only statements back is described as a statement row, not an email", () => {
  const row: Pick<Transaction, "payment_verification" | "extraction_quality" | "source_modes"> = {
    payment_verification: "verified",
    extraction_quality: "complete",
    source_modes: ["gpay_statement"],
  };
  assert.equal(paymentLabel(row), "Payment listed in your Google Pay statement");
  assert.equal(extractionLabel(row), "Every detail read from the statement");
  assert.equal(paymentLabel({ ...row, source_modes: ["gpay_statement", "gmail"] }), "Payment confirmed by a bank or card email");
});
