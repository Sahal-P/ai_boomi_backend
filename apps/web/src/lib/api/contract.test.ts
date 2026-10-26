import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { z } from "zod";
import { onSessionEvent } from "../session-events.ts";
import { answerSchema, askQuestion, displayLang, speechFor, transcribeAudio } from "./assistant.ts";
import { ApiError, failure, requestJson } from "./http.ts";
import { categoryLabels, extractionLabel, obligationKindLabels, paymentLabel, reasonFor, sourceLabels, sourceSender } from "../labels.ts";
import { getDemo } from "./demo.ts";
import { fileProblem, getImportIssues, getImportRun, getImports, importRunSchema, issueSchema } from "./imports.ts";
import { baseTransactionSchema, commitmentSchema, getObligation, getObligations, getSummary, inputPaise, simulate, summarySchema } from "./money.ts";
import { deletionPreviewSchema, exportRecords, getIsolation, previewDeletion } from "./privacy.ts";
import {
  decide,
  getMergeCandidates,
  getTransaction,
  getTransactionPage,
  pageSchema,
  previewDecision,
  previewSchema,
  recordQueryString,
  undoDecision,
  type DecisionRequest,
} from "./transactions.ts";

const read = async (path: string) =>
  z.record(z.string(), z.unknown()).parse(JSON.parse(await readFile(new URL(path, import.meta.url), "utf8")));
// Synthetic contract states published by the backend owner (docs/ux-round/fixtures).
const contract = await read("../../../../../docs/ux-round/fixtures/contract-v1.json");
// Phase-1 PostgreSQL HTTP examples: older shapes the household UI must not mistake for v1.
const phase1 = await read("../../../../../docs/handoffs/agent-1-api-examples.json");

test("v1 contract fixtures validate against the runtime schemas", () => {
  const summary = summarySchema.parse(contract.summary_partial_overdue);
  assert.equal(summary.coverage.state, "partial");
  assert.equal(summary.unresolved_commitments_minor, 100000);
  assert.equal(pageSchema.parse(contract.transactions_pending).items[0]?.payment_verification, "unverified");
  const empty = pageSchema.parse(contract.transactions_filtered_empty);
  assert.equal(empty.total, 0);
  assert.equal(empty.unresolved_total, 4, "a filtered-empty page still reports the whole queue");
  assert.equal(previewSchema.parse(contract.decision_preview).after_summary.estimated_unallocated_minor, 805000);
  assert.equal(issueSchema.parse(contract.issue).retry_strategy, "select_original_files");
  assert.equal(deletionPreviewSchema.parse(contract.deletion_preview).backup_retention_days, 7);
  for (const key of ["queued", "running", "complete", "partial", "failed", "interrupted", "cancelled"]) {
    assert.equal(importRunSchema.parse(contract[`import_${key}`]).outcome, key);
  }
});

test("a phase-1 summary without dataset, version or coverage is rejected, not shown as complete", () => {
  assert.equal(summarySchema.safeParse(phase1.money_summary).success, false);
  assert.equal(summarySchema.safeParse({ ...summarySchema.parse(contract.summary_partial_overdue), dataset: "demo" }).success, false);
  assert.equal(z.array(baseTransactionSchema).parse(phase1.transactions).length, 26);
  assert.throws(() => summarySchema.parse({ ...summarySchema.parse(contract.summary_partial_overdue), tracked_income_minor: 12.5 }));
});

test("error envelopes keep only the code and request id, and 401 signals session expiry", async () => {
  let expired = 0;
  const stop = onSessionEvent("expired", () => (expired += 1));
  const envelope = z.object({ error: z.object({ code: z.string(), request_id: z.string() }) });
  const unauthorised = envelope.parse(contract.error_401_session_required);
  const error = await failure(Response.json(unauthorised, { status: 401 }));
  assert.equal(error.kind, "session");
  assert.equal(error.code, "session_required");
  assert.equal(error.requestId, "40000000-0000-4000-8000-000000000001");
  assert.ok(!error.message.includes("requested task"));
  const conflict = await failure(Response.json(contract.error_409_version_conflict, { status: 409 }));
  assert.equal(conflict.kind, "conflict");
  const wrongPassword = await failure(
    Response.json({ error: { code: "invalid_credentials", message: "x", request_id: "r-1" } }, { status: 401 }),
  );
  assert.equal(wrongPassword.code, "invalid_credentials");
  stop();
  assert.equal(expired, 1, "a wrong password is not an expired session");
});

test("timeouts and network failures are classified without leaking details", async (t) => {
  const hang = t.mock.method(globalThis, "fetch", async (_input: string, init: RequestInit) =>
    new Promise<Response>((_resolve, reject) => init.signal?.addEventListener("abort", () => reject(init.signal?.reason))),
  );
  await assert.rejects(requestJson("/api/v1/example", z.object({}), { timeoutMs: 5 }), (error: unknown) =>
    error instanceof ApiError && error.kind === "timeout",
  );
  hang.mock.restore();
  t.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("connect ECONNREFUSED private-host");
  });
  await assert.rejects(requestJson("/api/v1/example", z.object({})), (error: unknown) =>
    error instanceof ApiError && error.kind === "network" && !error.message.includes("private-host"),
  );
});

test("save-and-confirm sends one version-checked atomic decision", async (t) => {
  const id = "10000000-0000-4000-8000-000000000001";
  const request: DecisionRequest = { expected_version: "42", action: "confirm", correction: { amount_minor: 95000 } };
  assert.deepEqual(request, contract.decision_request);
  t.mock.method(globalThis, "fetch", async (input: string, init: RequestInit) => {
    assert.equal(input, `http://127.0.0.1:8000/api/v1/transactions/${id}/decisions`);
    assert.equal(init.method, "POST");
    assert.equal(init.credentials, "omit");
    assert.deepEqual(JSON.parse(String(init.body)), contract.decision_request);
    return Response.json(contract.error_409_decision_conflict, { status: 409 });
  });
  await assert.rejects(decide(id, request), (error: unknown) => error instanceof ApiError && error.code === "decision_conflict");
});

test("undo posts the captured version to the decision's undo route", async (t) => {
  t.mock.method(globalThis, "fetch", async (input: string, init: RequestInit) => {
    assert.ok(input.endsWith("/api/v1/transactions/tx-1/decisions/d-1/undo"));
    assert.deepEqual(JSON.parse(String(init.body)), { expected_version: "43" });
    return Response.json(contract.error_409_version_conflict, { status: 409 });
  });
  await assert.rejects(undoDecision("tx-1", "d-1", "43"), ApiError);
});

test("record queries: the review queue spans every month unless one is chosen", () => {
  const base = { limit: 50, offset: 0 } as const;
  assert.equal(recordQueryString({ ...base, scope: "unresolved", period: null, status: "confirmed" }), "?scope=unresolved&limit=50&offset=0");
  assert.equal(
    recordQueryString({ ...base, scope: "unresolved", period: { year: 2026, month: 9 } }),
    "?scope=unresolved&period=month&year=2026&month=9&limit=50&offset=0",
  );
  assert.equal(recordQueryString({ ...base, scope: "month", period: null }), "?scope=month&period=current_month&limit=50&offset=0");
  assert.equal(
    recordQueryString({ ...base, scope: "all", period: null, q: "  Amazon ", offset: 200, data_version: "42" }),
    "?scope=all&q=Amazon&limit=50&offset=200&data_version=42",
  );
});

test("money input stays integer paise and rejects ambiguous values", () => {
  assert.equal(inputPaise("5000.05"), 500005);
  assert.equal(inputPaise("5,000"), 500000);
  for (const invalid of ["-1", "1e3", "0", "10.999", "NaN", ""]) assert.equal(inputPaise(invalid), null);
});

test("uploads are checked locally before anything is sent", () => {
  assert.equal(fileProblem({ name: "alert.eml", size: 10, type: "message/rfc822" }), null);
  assert.equal(fileProblem({ name: "alert.EML", size: 10, type: "" }), null);
  assert.equal(fileProblem({ name: "alert.pdf", size: 10, type: "application/pdf" }), "not_eml");
  assert.equal(fileProblem({ name: "empty.eml", size: 0, type: "" }), "empty");
  assert.equal(fileProblem({ name: "big.eml", size: 2 * 1024 * 1024 + 1, type: "" }), "too_large");
});

const answer = {
  intent: "spend_total",
  policy: "answer",
  display_text: "Synthetic answer.",
  speech_text: "Synthetic answer.",
  speech_language: "hi",
  display_language: "hi",
  display_script: "Latn",
  facts: [{ key: "pending_review_count", label: "Review baaki", amount_minor: null, count: 2, currency: null }],
  simulation: null,
  evidence_transactions: [],
  evidence_total: 0,
  evidence_sampled: false,
  warnings: ["incomplete_coverage"],
  warning_labels: { incomplete_coverage: "Coverage poori nahi hai" },
  data_version: "42",
  dataset: "household",
  resolved_period: { start: "2026-10-01", end: "2026-10-31", label: "October 2026" },
};

test("answers carry localized labels and separate display script from speech", () => {
  const parsed = answerSchema.parse(answer);
  assert.equal(displayLang(parsed), "hi-Latn");
  assert.equal(displayLang({ display_language: "ml", display_script: "Mlym" }), "ml");
  assert.equal(displayLang({ display_language: "en", display_script: "Latn" }), "en-IN");
  assert.equal(answerSchema.safeParse({ ...answer, facts: [{ ...answer.facts[0], label: "" }] }).success, false);
  assert.equal(answerSchema.safeParse({ ...answer, dataset: "demo" }).success, false);
});

test("speech failure never turns a JSON error into playable audio", async (t) => {
  const parsed = answerSchema.parse(answer);
  t.mock.method(globalThis, "fetch", async () => Response.json({ error: { code: "provider_unavailable", request_id: "r-2" } }, { status: 503 }));
  await assert.rejects(speechFor(parsed), (error: unknown) => error instanceof ApiError && error.kind === "unavailable");
  assert.equal(parsed.display_text, "Synthetic answer.");
});

test("transcription uses bounded multipart audio and validates detected language", async (t) => {
  t.mock.method(globalThis, "fetch", async (_input: string, init: RequestInit) => {
    assert.ok(init.body instanceof FormData);
    assert.ok(init.body.get("audio") instanceof Blob);
    assert.equal(init.credentials, "omit");
    return Response.json({ transcript: "synthetic", detected_language: "ml" });
  });
  assert.equal((await transcribeAudio(new Blob(["synthetic"], { type: "audio/webm" }))).detected_language, "ml");
  await assert.rejects(transcribeAudio(new Blob([new Uint8Array(3 * 1024 * 1024 + 1)])), ApiError);
});

test("typed summary client rejects malformed success without exposing it", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ private: "sensitive" }));
  await assert.rejects(getSummary(null), (error: unknown) => error instanceof ApiError && !error.message.includes("sensitive"));
});

// Responses captured from the real API by the backend owner (contract v1.2.0). The file lives on
// the backend branch, so this runs once both branches are assembled.
const actualHttp = new URL("../../../../../docs/ux-round/fixtures/actual-http-v1.json", import.meta.url);
test(
  "actual backend HTTP examples parse through the same clients the pages use",
  { skip: !existsSync(actualHttp) && "actual-http-v1.json arrives with the backend branch" },
  async (t) => {
    const actual = await read("../../../../../docs/ux-round/fixtures/actual-http-v1.json");
    let body: unknown = null;
    t.mock.method(globalThis, "fetch", async () => Response.json(body));
    const id = "10000000-0000-4000-8000-000000000001";
    const query = { scope: "all", period: null, limit: 50, offset: 0 } as const;
    const decision: DecisionRequest = { expected_version: "1", action: "confirm" };
    const calls: Record<string, () => Promise<unknown>> = {
      demo: () => getDemo(),
      summary: () => getSummary(null),
      transaction_page: () => getTransactionPage(query),
      filtered_empty: () => getTransactionPage(query),
      transaction_detail: () => getTransaction(id),
      merge_candidates: () => getMergeCandidates(id),
      obligations: () => getObligations("unresolved"),
      obligation_detail: () => getObligation(id),
      import_status: () => getImportRun(id),
      import_history: () => getImports(0),
      import_issues: () => getImportIssues(id, 0),
      isolation: () => getIsolation(),
      decision_preview: () => previewDecision(id, decision),
      decision_result: () => decide(id, decision),
      undo_result: () => undoDecision(id, id, "1"),
      simulation: () => simulate(100000),
      deletion_preview: () => previewDeletion(null),
      structured_export: () => exportRecords("1"),
    };
    for (const style of ["en", "hi", "ml", "hinglish", "manglish", "period_clarification"]) {
      calls[`assistant_${style}`] = () => askQuestion("synthetic", "auto");
    }
    for (const [key, call] of Object.entries(calls)) {
      body = actual[key];
      await assert.doesNotReject(call(), `actual ${key} response`);
    }
    assert.deepEqual(Object.keys(actual.decision_request as object).sort(), ["action", "correction", "expected_version"]);
  },
);

test("WhatsApp screenshot sources validate and read as the household's own message", () => {
  const fixture = (key: string) => z.record(z.string(), z.unknown()).parse(contract[key]);
  const pending = fixture("transactions_pending");
  const page = z.object({ items: z.array(z.record(z.string(), z.unknown())) }).parse(pending);
  const item = { ...page.items[0], source_modes: ["whatsapp_image"] };
  assert.deepEqual(pageSchema.parse({ ...pending, items: [item] }).items[0]?.source_modes, ["whatsapp_image"]);
  const run = importRunSchema.parse({ ...fixture("import_complete"), mode: "whatsapp_image", retry_strategy: "none" });
  assert.equal(sourceLabels[run.mode], "WhatsApp screenshot");
  const issue = issueSchema.parse({ ...fixture("issue"), source_mode: "whatsapp_image", retryable: false, retry_strategy: "none" });
  assert.equal(issue.source_mode, "whatsapp_image");
  assert.equal(sourceSender({ source: "whatsapp_image", sender_domain: "whatsapp.invalid" }), "Your WhatsApp screenshot");
  assert.equal(sourceSender({ source: "gmail", sender_domain: "alerts.example.test" }), "alerts.example.test");
  assert.equal(
    recordQueryString({ limit: 50, offset: 0, scope: "all", period: null, source: "whatsapp_image" }),
    "?scope=all&source=whatsapp_image&limit=50&offset=0",
  );
});

test("pilot voice records, village categories and spoken loan dues validate and read plainly", () => {
  const fixture = (key: string) => z.record(z.string(), z.unknown()).parse(contract[key]);
  const pending = fixture("transactions_pending");
  const page = z.object({ items: z.array(z.record(z.string(), z.unknown())) }).parse(pending);
  const item = { ...page.items[0], source_modes: ["whatsapp_voice"], category: "farming" };
  const parsed = pageSchema.parse({ ...pending, items: [item] }).items[0];
  assert.deepEqual(parsed?.source_modes, ["whatsapp_voice"]);
  assert.equal(parsed && categoryLabels[parsed.category], "Farming");
  const run = importRunSchema.parse({ ...fixture("import_complete"), mode: "whatsapp_voice", retry_strategy: "none" });
  assert.equal(sourceLabels[run.mode], "WhatsApp voice note");
  assert.equal(sourceSender({ source: "whatsapp_voice", sender_domain: "whatsapp.invalid" }), "Your WhatsApp voice note");
  const voice = { source_modes: ["whatsapp_voice" as const], extraction_quality: "partial" as const };
  assert.equal(paymentLabel({ ...voice, payment_verification: "verified" }), "Confirmed by you from a voice note");
  assert.equal(extractionLabel(voice), "Some details were unclear in your voice note");
  const reason = reasonFor({ status: "needs_review", review_reason: "unverified_payment", source_modes: ["whatsapp_voice"] });
  assert.match(reason?.detail ?? "", /voice note/);
  assert.doesNotMatch(reason?.detail ?? "", /email|screenshot/);
  const due = commitmentSchema.parse({
    id: "40000000-0000-4000-8000-000000000001",
    kind: "loan",
    label: "समूह की किस्त",
    amount_minor: 120000,
    currency: "INR",
    due_date: "2026-11-10",
    status: "upcoming",
    confidence: 1,
    source_event_id: null,
    paid_transaction_id: null,
    version: "7:2026-10-26",
    dataset: "household",
    liability_state: "upcoming",
    uncertain: false,
  });
  assert.equal(obligationKindLabels[due.kind], "Loan");
});

test("screenshot-only records never borrow email or bank-email wording", () => {
  const shot = { source_modes: ["whatsapp_image"] as const, extraction_quality: "complete" as const };
  const mixed = { source_modes: ["eml_upload", "whatsapp_image"] as const, extraction_quality: "complete" as const };
  assert.equal(paymentLabel({ ...shot, source_modes: [...shot.source_modes], payment_verification: "verified" }), "Confirmed by you from a payment screenshot");
  assert.equal(paymentLabel({ ...mixed, source_modes: [...mixed.source_modes], payment_verification: "verified" }), "Payment confirmed by a bank or card email");
  assert.equal(extractionLabel({ ...shot, source_modes: [...shot.source_modes] }), "All key details found in the screenshot");
  const reason = reasonFor({ status: "needs_review", review_reason: "unverified_payment", source_modes: ["whatsapp_image"] });
  assert.match(reason?.detail ?? "", /screenshot/);
  assert.doesNotMatch(reason?.detail ?? "", /email/);
  assert.match(reasonFor({ status: "needs_review", review_reason: "unverified_payment" })?.detail ?? "", /email/);
});
