import assert from "node:assert/strict";
import { test } from "node:test";
import type { ImportRun } from "./api/imports.ts";
import { importOutcome } from "./import-outcome.ts";

const base: ImportRun = {
  id: "30000000-0000-4000-8000-000000000001",
  mode: "gmail",
  status: "completed",
  headers_checked: 40,
  candidates_found: 15,
  emails_processed: 15,
  events_extracted: 4,
  transactions_created: 4,
  duplicates_merged: 0,
  needs_review: 4,
  non_financial_skipped: 9,
  failed: 2,
  error_code: null,
  started_at: "2026-10-24T09:00:00+05:30",
  finished_at: "2026-10-24T09:00:10+05:30",
  outcome: "partial",
  retryable: true,
  retry_strategy: "refetch_gmail",
  cancel_requested: false,
  window_start: "2026-09-24",
  window_end: "2026-10-24",
  truncated: false,
  data_version: "42",
  can_continue: false,
};

test("the audited partial import leads with review, not success", () => {
  const copy = importOutcome(base);
  assert.equal(copy.title, "4 records need review · 2 emails couldn't be read");
  assert.deepEqual(copy.primary, { kind: "review", label: "Review 4 records" });
  assert.deepEqual(copy.secondary, [{ kind: "retry_gmail", label: "Retry 2 emails" }]);
  assert.ok(copy.detail.some((line) => line.includes("don't change your confirmed totals")));
});

test("clean completion where every new record needs review makes Review primary", () => {
  const copy = importOutcome({ ...base, failed: 0, outcome: "complete", retryable: false });
  assert.equal(copy.title, "4 new records need review");
  assert.equal(copy.primary?.kind, "review");
});

test("a scan with nothing new says so honestly", () => {
  const copy = importOutcome({ ...base, failed: 0, outcome: "complete", transactions_created: 0, needs_review: 0 });
  assert.equal(copy.title, "No new records found");
  assert.ok(copy.detail[0]?.includes("totals are unchanged"));
});

test("interrupted uploads ask for the original files instead of implying a resume", () => {
  const copy = importOutcome({ ...base, mode: "eml_upload", status: "failed", outcome: "interrupted", retry_strategy: "select_original_files", failed: 0 });
  assert.equal(copy.title, "Import was interrupted");
  assert.deepEqual(copy.primary, { kind: "select_files", label: "Select the original files again" });
  assert.ok(copy.detail.some((line) => line.includes("original .eml files")));
});

test("a stopped WhatsApp voice capture asks to say it again, not to retry emails", () => {
  const copy = importOutcome({ ...base, mode: "whatsapp_voice", status: "failed", outcome: "interrupted", retryable: false, retry_strategy: "none", failed: 0 });
  assert.ok(copy.detail.includes("Voice notes aren't kept, so say it again on WhatsApp."));
  assert.ok(!copy.detail.some((line) => line.includes("emails")));
});

test("cancelled imports keep saved records and offer review", () => {
  const copy = importOutcome({ ...base, status: "failed", outcome: "cancelled", cancel_requested: true, failed: 0 });
  assert.equal(copy.title, "Import cancelled");
  assert.equal(copy.primary?.kind, "review");
});

test("a truncated Gmail scan offers to continue its window", () => {
  const copy = importOutcome({ ...base, failed: 0, needs_review: 0, outcome: "complete", truncated: true, can_continue: true });
  assert.equal(copy.primary?.kind, "continue_gmail");
  assert.ok(copy.detail.some((line) => line.includes("reached its limit")));
});

test("running imports explain progress and that leaving is safe", () => {
  const copy = importOutcome({ ...base, status: "running", outcome: "running", emails_processed: 6 });
  assert.equal(copy.tone, "progress");
  assert.ok(copy.detail[0]?.includes("6 of 15"));
  assert.equal(copy.primary, null);
});
