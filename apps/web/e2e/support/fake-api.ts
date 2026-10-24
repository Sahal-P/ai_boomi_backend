import { readFileSync } from "node:fs";

/**
 * TEST-ONLY in-memory double of the FinBoy API contract v1.1 (docs/ux-round/api-contract.md).
 * All data is synthetic. It exists to drive browser journeys before and alongside the real
 * backend; it is never imported by application code and proves nothing about live integration.
 */

type Json = Record<string, unknown>;
export type FakeResponse = { status: number; headers?: Record<string, string>; body?: unknown; raw?: string | Buffer };
export type FakeRequest = { method: string; path: string; query: URLSearchParams; body: unknown; origin: string | null };

type Direction = "in" | "out";
type Status = "confirmed" | "needs_review" | "rejected" | "merged" | "failed";
type Reason = "low_confidence" | "merchant_uncertain" | "possible_duplicate" | "category_uncertain" | "unverified_payment" | null;
type Tx = {
  id: string;
  direction: Direction;
  kind: string;
  amount_minor: number;
  currency: "INR";
  merchant: string;
  category: string;
  occurred_at: string;
  status: Status;
  confidence: number;
  review_reason: Reason;
  reference_id: string | null;
  payment_instrument: string | null;
  account_last4: string | null;
  possible_duplicate_of_id: string | null;
  linked_transaction_id: string | null;
  merged_into_id: string | null;
  dataset: "household" | "quarantined";
  source_modes: ("gmail" | "eml_upload")[];
  source_count: number;
  extraction_quality: "complete" | "partial";
  payment_verification: "verified" | "unverified" | "failed";
  version: string;
};
type Decision = { id: string; action: string; created_at: string; undone_at: string | null; can_undo: boolean; before: Tx; after: string; others: Tx[] };
type Obligation = {
  id: string;
  kind: "bill" | "emi" | "subscription" | "sip";
  label: string;
  amount_minor: number;
  currency: "INR";
  due_date: string;
  status: "upcoming" | "paid" | "dismissed";
  confidence: number;
  source_event_id: string | null;
  paid_transaction_id: string | null;
  version: string;
  dataset: "household";
  liability_state: "upcoming" | "overdue" | "paid" | "dismissed";
  uncertain: boolean;
};
type ImportRun = Json & { id: string; outcome: string; mode: string; data_version: string };

export const TODAY = "2026-10-24";
export const PASSWORD = "synthetic-household-password";
const NOW = "2026-10-24T09:30:00+05:30";
const uuid = (prefix: string, index: number) => `${prefix}-0000-4000-8000-${index.toString(16).padStart(12, "0")}`;
export const ids = {
  duplicate: uuid("10000000", 1),
  duplicateTarget: uuid("10000000", 2),
  unverified: uuid("10000000", 3),
  merchantUnclear: uuid("10000000", 4),
  septemberReview: uuid("10000000", 5),
  salary: uuid("10000000", 6),
  refund: uuid("10000000", 7),
  transfer: uuid("10000000", 8),
  failedPayment: uuid("10000000", 9),
  partialImport: uuid("30000000", 1),
  runningImport: uuid("30000000", 2),
  uploadInterrupted: uuid("30000000", 3),
  completeImport: uuid("30000000", 4),
  obligationOverdue: uuid("50000000", 1),
  obligationUpcoming: uuid("50000000", 2),
  connection: uuid("60000000", 1),
};

const envelope = (status: number, code: string): FakeResponse => ({
  status,
  body: { error: { code, message: "The requested task could not be completed.", request_id: uuid("40000000", status) } },
});

function tx(index: number, values: Partial<Tx>): Tx {
  return {
    id: uuid("10000000", index),
    direction: "out",
    kind: "purchase",
    amount_minor: 50000,
    currency: "INR",
    merchant: `Sample Store ${index}`,
    category: "shopping",
    occurred_at: "2026-10-10T10:00:00+05:30",
    status: "confirmed",
    confidence: 0.95,
    review_reason: null,
    reference_id: null,
    payment_instrument: null,
    account_last4: null,
    possible_duplicate_of_id: null,
    linked_transaction_id: null,
    merged_into_id: null,
    dataset: "household",
    source_modes: ["gmail"],
    source_count: 1,
    extraction_quality: "complete",
    payment_verification: "verified",
    version: "1",
    ...values,
  };
}

export type Scenario = {
  authRequired?: boolean;
  signedIn?: boolean;
  bulk?: number;
  connection?: "active" | "paused" | "error" | "none";
  emptyLedger?: boolean;
};

export class FakeFinBoyApi {
  version = 100;
  authRequired: boolean;
  signedIn: boolean;
  transactions: Tx[] = [];
  decisions = new Map<string, Decision[]>();
  obligations: Obligation[] = [];
  imports = new Map<string, ImportRun>();
  connection: Json | null;
  failures: { pattern: RegExp; method: string | null; response: FakeResponse; times: number }[] = [];
  delays: { pattern: RegExp; ms: number }[] = [];
  outcomes: string[] = [];
  requests: { method: string; path: string; body: unknown }[] = [];
  private polls = 0;
  private counter = 900;

  constructor(scenario: Scenario = {}) {
    this.authRequired = scenario.authRequired ?? true;
    this.signedIn = scenario.signedIn ?? true;
    const status = scenario.connection ?? "active";
    this.connection =
      status === "none"
        ? null
        : { id: ids.connection, provider: "gmail", account_email_masked: "ho***@example.test", status, last_synced_at: "2026-10-24T09:00:00+05:30" };
    if (!scenario.emptyLedger) this.seed(scenario.bulk ?? 0);
  }

  private seed(bulk: number) {
    this.transactions = [
      tx(1, { merchant: "Sample Books", amount_minor: 79900, status: "needs_review", review_reason: "possible_duplicate", possible_duplicate_of_id: ids.duplicateTarget, payment_verification: "unverified", occurred_at: "2026-10-21T19:05:00+05:30" }),
      tx(2, { merchant: "Sample Books", amount_minor: 79900, occurred_at: "2026-10-21T19:00:00+05:30", source_count: 2, source_modes: ["gmail", "eml_upload"] }),
      tx(3, { merchant: "Sample Marketplace", amount_minor: 184000, status: "needs_review", review_reason: "unverified_payment", payment_verification: "unverified", occurred_at: "2026-10-20T12:00:00+05:30", confidence: 1 }),
      tx(4, { merchant: "Unknown merchant", amount_minor: 42000, status: "needs_review", review_reason: "merchant_uncertain", category: "other", extraction_quality: "partial", occurred_at: "2026-10-18T08:30:00+05:30", source_modes: ["eml_upload"] }),
      tx(5, { merchant: "Sample Pharmacy", amount_minor: 31000, status: "needs_review", review_reason: "category_uncertain", category: "other", occurred_at: "2026-09-28T17:00:00+05:30" }),
      tx(6, { merchant: "Sample Employer", direction: "in", kind: "salary", category: "salary", amount_minor: 6200000, occurred_at: "2026-10-01T09:00:00+05:30" }),
      tx(7, { merchant: "Sample Books", direction: "in", kind: "refund", amount_minor: 20000, occurred_at: "2026-10-22T10:00:00+05:30", linked_transaction_id: ids.duplicateTarget }),
      tx(8, { merchant: "Own savings account", kind: "transfer", category: "transfer", amount_minor: 1000000, occurred_at: "2026-10-05T10:00:00+05:30" }),
      tx(9, { merchant: "Sample Fuel", status: "failed", payment_verification: "failed", amount_minor: 250000, category: "transport", occurred_at: "2026-10-12T10:00:00+05:30" }),
      tx(10, { merchant: "Sample Cafe", amount_minor: 45000, category: "food_dining", occurred_at: "2026-10-15T13:00:00+05:30" }),
      tx(11, { merchant: "Sample Grocer", amount_minor: 312000, category: "groceries", occurred_at: "2026-10-09T18:00:00+05:30" }),
      tx(12, { merchant: "Mixed sample record", amount_minor: 99900, dataset: "quarantined", occurred_at: "2026-10-03T10:00:00+05:30" }),
    ];
    for (let index = 0; index < bulk; index += 1) {
      const day = String(1 + (index % 24)).padStart(2, "0");
      this.transactions.push(
        tx(100 + index, { merchant: `Sample Bulk ${String(index + 1).padStart(3, "0")}`, amount_minor: 1000 + index, category: "groceries", occurred_at: `2026-10-${day}T07:${String(index % 60).padStart(2, "0")}:00+05:30` }),
      );
    }
    this.obligations = [
      { id: ids.obligationOverdue, kind: "bill", label: "Sample electricity bill", amount_minor: 100000, currency: "INR", due_date: "2026-10-23", status: "upcoming", confidence: 0.6, source_event_id: null, paid_transaction_id: null, version: String(this.version), dataset: "household", liability_state: "overdue", uncertain: true },
      { id: ids.obligationUpcoming, kind: "subscription", label: "Sample streaming plan", amount_minor: 64900, currency: "INR", due_date: "2026-10-29", status: "upcoming", confidence: 0.95, source_event_id: null, paid_transaction_id: null, version: String(this.version), dataset: "household", liability_state: "upcoming", uncertain: false },
    ];
    const run = (id: string, values: Json): ImportRun => ({
      id,
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
      failed: 0,
      error_code: null,
      started_at: "2026-10-24T09:00:00+05:30",
      finished_at: "2026-10-24T09:00:40+05:30",
      outcome: "complete",
      retryable: false,
      retry_strategy: "none",
      cancel_requested: false,
      window_start: "2026-09-24",
      window_end: TODAY,
      truncated: false,
      data_version: String(this.version),
      can_continue: false,
      ...values,
    });
    this.imports.set(ids.partialImport, run(ids.partialImport, { failed: 2, outcome: "partial", retryable: true, retry_strategy: "refetch_gmail" }));
    this.imports.set(ids.runningImport, run(ids.runningImport, { status: "running", outcome: "running", emails_processed: 3, finished_at: null, transactions_created: 0, needs_review: 0, non_financial_skipped: 0 }));
    this.imports.set(ids.uploadInterrupted, run(ids.uploadInterrupted, { mode: "eml_upload", status: "failed", outcome: "interrupted", error_code: "import_failed", retryable: true, retry_strategy: "select_original_files", window_start: null, window_end: null, transactions_created: 1, needs_review: 1, failed: 0 }));
    this.imports.set(ids.completeImport, run(ids.completeImport, { started_at: "2026-10-20T09:00:00+05:30", finished_at: "2026-10-20T09:00:20+05:30" }));
  }

  // ── Test controls ──────────────────────────────────────────────────────────
  failNext(pattern: RegExp, status: number, code: string, times = 1, method: string | null = null) {
    this.failures.push({ pattern, method, response: envelope(status, code), times });
  }
  delay(pattern: RegExp, ms: number) {
    this.delays.push({ pattern, ms });
  }
  bump() {
    this.version += 1;
    return String(this.version);
  }
  get unresolved() {
    return this.transactions.filter((item) => item.status === "needs_review" && item.dataset === "household");
  }

  // ── Dispatcher ─────────────────────────────────────────────────────────────
  async handle(request: FakeRequest, appOrigin: string): Promise<FakeResponse> {
    const { method, path, query, body } = request;
    this.requests.push({ method, path: `${path}${query.size ? `?${query.toString()}` : ""}`, body });
    for (const item of this.delays) if (item.pattern.test(path)) await new Promise((resolve) => setTimeout(resolve, item.ms));
    const failure = this.failures.find((item) => item.times > 0 && item.pattern.test(path) && (!item.method || item.method === method));
    if (failure) {
      failure.times -= 1;
      return failure.response;
    }
    const open = ["/api/v1/health", "/api/v1/auth/session", "/api/v1/auth/login", "/api/v1/demo"].includes(path);
    if (this.authRequired && !open && !this.signedIn) return envelope(401, "authentication_required");
    if (["POST", "PATCH", "DELETE"].includes(method) && request.origin !== appOrigin) return envelope(403, "origin_not_allowed");
    return this.route(method, path, query, (body ?? {}) as Json);
  }

  private route(method: string, path: string, query: URLSearchParams, body: Json): FakeResponse {
    const ok = (value: unknown, status = 200): FakeResponse => ({ status, body: value });
    let match: RegExpMatchArray | null;
    if (path === "/api/v1/health") return ok({ service: "finboy-api", version: "0.1.0", status: "ok", database: "connected" });
    if (path === "/api/v1/auth/session") return ok({ authenticated: !this.authRequired || this.signedIn, required: this.authRequired });
    if (path === "/api/v1/auth/login" && method === "POST") {
      if (body.password !== PASSWORD) return envelope(401, "invalid_credentials");
      this.signedIn = true;
      return ok({ authenticated: true });
    }
    if (path === "/api/v1/auth/logout") {
      this.signedIn = false;
      return ok({ authenticated: false });
    }
    if (path === "/api/v1/demo") return ok(this.demo());
    if (path === "/api/v1/connections") return ok(this.connection ? [this.connection] : []);
    if (path === "/api/v1/connections/gmail/authorize") {
      // Cross-host OAuth double: Google consent is never contacted from tests.
      const outcome = this.outcomes.shift() ?? "denied";
      return { status: 302, headers: { location: outcome === "denied" ? "/connect?error=consent_denied" : `/import/${ids.partialImport}` } };
    }
    if ((match = path.match(/^\/api\/v1\/connections\/([^/]+)\/(sync|pause|resume)$/)) && this.connection) {
      if (match[2] === "sync") {
        this.polls = 0;
        return ok({ import_run_id: ids.runningImport }, 202);
      }
      this.connection = { ...this.connection, status: match[2] === "pause" ? "paused" : "active" };
      this.bump();
      return ok({ status: "ok" });
    }
    if ((match = path.match(/^\/api\/v1\/connections\/([^/]+)$/)) && method === "DELETE") {
      this.connection = null;
      this.bump();
      return ok({ status: "ok" });
    }
    if (path === "/api/v1/money/summary") return ok(this.summary(query));
    if (path === "/api/v1/money/simulations" && method === "POST") return this.simulation(body);
    if (path === "/api/v1/money/obligations") {
      const status = query.get("status") ?? "unresolved";
      const items = this.obligations.filter((item) => status === "all" || (status === "unresolved" ? item.status === "upcoming" : item.status === status));
      return ok({ items, data_version: String(this.version) });
    }
    if ((match = path.match(/^\/api\/v1\/money\/obligations\/([^/]+)$/))) return this.obligation(match[1] ?? "", method, body);
    if (path === "/api/v1/transactions/page") return this.page(query);
    if ((match = path.match(/^\/api\/v1\/transactions\/([^/]+)\/merge-candidates$/))) return this.candidates(match[1] ?? "");
    if ((match = path.match(/^\/api\/v1\/transactions\/([^/]+)\/decision-preview$/))) return this.preview(match[1] ?? "", body);
    if ((match = path.match(/^\/api\/v1\/transactions\/([^/]+)\/decisions\/([^/]+)\/undo$/))) return this.undo(match[1] ?? "", match[2] ?? "", body);
    if ((match = path.match(/^\/api\/v1\/transactions\/([^/]+)\/decisions$/))) return this.decide(match[1] ?? "", body);
    if ((match = path.match(/^\/api\/v1\/transactions\/([^/]+)$/))) {
      const item = this.transactions.find((row) => row.id === match?.[1]);
      return item ? ok(this.detail(item)) : envelope(404, "not_found");
    }
    if (path === "/api/v1/imports" && method === "GET") {
      const items = [...this.imports.values()].sort((a, b) => String(b.started_at).localeCompare(String(a.started_at)));
      return ok({ items, total: items.length, next_offset: null });
    }
    if (path === "/api/v1/imports/eml" && method === "POST") {
      const id = uuid("30000000", this.counter++);
      this.imports.set(id, { ...(this.imports.get(ids.completeImport) as ImportRun), id, mode: "eml_upload", started_at: NOW, data_version: this.bump() });
      return ok({ import_run_id: id }, 202);
    }
    if ((match = path.match(/^\/api\/v1\/imports\/([^/]+)(?:\/(issues|retry|cancel|continue))?$/))) return this.importRoute(match[1] ?? "", match[2] ?? null, body);
    if (path === "/api/v1/privacy/isolation") return ok({ data_version: String(this.version), demo_only_transactions: 3, mixed_transactions: 1, demo_only_obligations: 0, quarantined_obligations: 0 });
    if (path === "/api/v1/privacy/audit-events") {
      return ok([
        { id: uuid("70000000", 1), event_type: "import.completed", subject_type: "import_run", subject_id: ids.partialImport, created_at: "2026-10-24T09:00:40+05:30" },
        { id: uuid("70000000", 2), event_type: "gmail.connected", subject_type: "mail_connection", subject_id: ids.connection, created_at: "2026-10-24T08:59:00+05:30" },
      ]);
    }
    if (path === "/api/v1/privacy/deletion-preview") {
      return ok({ version: String(this.version), connection_id: (body.connection_id as string | undefined) ?? null, source_count: 14, event_count: 12, removed_transaction_count: 10, retained_shared_transaction_count: 1, removed_obligation_count: 2, retained_shared_obligation_count: 0, first_received_at: "2026-09-24T09:00:00+05:30", last_received_at: "2026-10-24T09:00:00+05:30", backup_retention_days: 7 });
    }
    if (path === "/api/v1/privacy/delete") {
      if (body.expected_version !== String(this.version)) return envelope(409, "version_conflict");
      this.transactions = this.transactions.filter((item) => item.dataset === "quarantined");
      return ok({ status: "ok", data_version: this.bump() });
    }
    if (path === "/api/v1/privacy/export") {
      if (body.expected_version !== String(this.version)) return envelope(409, "version_conflict");
      return {
        status: 200,
        headers: { "content-type": "application/json", "content-disposition": 'attachment; filename="finboy-export-2026-10-24.json"' },
        raw: JSON.stringify({ schema_version: "1.0", dataset: "household", exported_at: NOW, data_version: String(this.version), transactions: this.transactions.filter((t) => t.dataset === "household").map(({ id, merchant, amount_minor }) => ({ id, merchant, amount_minor })), commitments: [], revisions: [] }),
      };
    }
    if (path === "/api/v1/privacy/task-outcomes") {
      this.requests.push({ method: "OUTCOME", path, body });
      return ok({ status: "ok" });
    }
    if (path === "/api/v1/assistant/ask") return this.ask(body);
    if (path === "/api/v1/assistant/speak") return this.speak();
    if (path === "/api/v1/assistant/transcribe") return ok({ transcript: "How much did I spend on food this month?", detected_language: "en" });
    if (path === "/api/v1/imports/demo") return envelope(409, "demo_read_only");
    return envelope(404, "not_found");
  }

  // ── Money ──────────────────────────────────────────────────────────────────
  summary(query: URLSearchParams | null = null) {
    const month = query?.get("period") === "month" ? Number(query.get("month")) : 10;
    const inMonth = (item: Tx) => Number(item.occurred_at.slice(5, 7)) === month && item.dataset === "household";
    const confirmed = this.transactions.filter((item) => item.status === "confirmed" && inMonth(item) && item.kind !== "transfer");
    const income = confirmed.filter((item) => item.direction === "in" && ["salary", "income_other"].includes(item.kind));
    const outflows = confirmed.filter((item) => item.direction === "out" || ["refund", "reversal"].includes(item.kind));
    const categories = new Map<string, { amount: number; count: number }>();
    for (const item of outflows) {
      const category = item.kind === "refund" ? "shopping" : item.category;
      const current = categories.get(category) ?? { amount: 0, count: 0 };
      categories.set(category, { amount: current.amount + (item.direction === "out" ? item.amount_minor : -item.amount_minor), count: current.count + 1 });
    }
    const sum = (rows: { amount_minor: number }[]) => rows.reduce((total, row) => total + row.amount_minor, 0);
    const outflowTotal = [...categories.values()].reduce((total, row) => total + row.amount, 0);
    const open = this.obligations.filter((item) => item.status === "upcoming");
    const overdue = open.filter((item) => item.liability_state === "overdue");
    const review = this.transactions.filter((item) => item.status === "needs_review" && inMonth(item));
    const incomeTotal = sum(income);
    const unresolved = sum(open);
    return {
      period_start: `2026-${String(month).padStart(2, "0")}-01`,
      period_end: month === 9 ? "2026-09-30" : "2026-10-31",
      as_of: TODAY,
      currency: "INR",
      tracked_income_minor: incomeTotal,
      confirmed_outflows_minor: outflowTotal,
      upcoming_commitments_minor: sum(open.filter((item) => item.liability_state === "upcoming")),
      overdue_commitments_minor: sum(overdue),
      uncertain_commitments_minor: sum(open.filter((item) => item.uncertain)),
      unresolved_commitments_minor: unresolved,
      overdue_commitment_count: overdue.length,
      estimated_unallocated_minor: incomeTotal - outflowTotal - unresolved,
      pending_review_count: review.length,
      pending_review_minor: sum(review),
      income_transaction_count: income.length,
      outflow_transaction_count: outflows.length,
      commitment_count: open.length,
      categories: [...categories.entries()]
        .map(([category, value]) => ({ category, amount_minor: value.amount, currency: "INR", transaction_count: value.count }))
        .sort((a, b) => Math.abs(b.amount_minor) - Math.abs(a.amount_minor)),
      evidence_transaction_ids: [...income, ...outflows].map((item) => item.id),
      dataset: "household",
      data_version: String(this.version),
      coverage: {
        sync_mode: "manual",
        last_successful_scan_at: "2026-10-24T09:00:00+05:30",
        window_start: "2026-09-24",
        window_end: TODAY,
        state: "partial",
        truncated: false,
        pending_review_count: this.unresolved.length,
        failed_source_count: 2,
        active_import_id: null,
        quarantined_count: this.transactions.filter((item) => item.dataset === "quarantined").length,
      },
    };
  }

  private simulation(body: Json): FakeResponse {
    const amount = Number(body.monthly_amount_minor);
    if (!Number.isInteger(amount) || amount <= 0) return envelope(422, "validation_error");
    const summary = this.summary();
    return {
      status: 200,
      body: {
        summary,
        proposed_monthly_minor: amount,
        remaining_after_proposal_minor: summary.estimated_unallocated_minor - amount,
        lines: [
          { label_key: "tracked_income", amount_minor: summary.tracked_income_minor, sign: "+" },
          { label_key: "confirmed_outflows", amount_minor: summary.confirmed_outflows_minor, sign: "-" },
          { label_key: "upcoming_commitments", amount_minor: summary.upcoming_commitments_minor, sign: "-" },
          { label_key: "overdue_commitments", amount_minor: summary.overdue_commitments_minor, sign: "-" },
          { label_key: "proposed_monthly", amount_minor: amount, sign: "-" },
        ],
        warnings: ["pending_review_items", "incomplete_coverage"],
        disclaimer_key: "cash_flow_model_not_investment_advice",
      },
    };
  }

  private obligation(id: string, method: string, body: Json): FakeResponse {
    const index = this.obligations.findIndex((item) => item.id === id);
    const item = this.obligations[index];
    if (!item) return envelope(404, "not_found");
    if (method === "PATCH") {
      if (body.expected_version !== item.version) return envelope(409, "version_conflict");
      const version = this.bump();
      const status = (body.status as Obligation["status"] | undefined) ?? item.status;
      const next: Obligation = {
        ...item,
        label: (body.label as string | undefined) ?? item.label,
        amount_minor: (body.amount_minor as number | undefined) ?? item.amount_minor,
        due_date: (body.due_date as string | undefined) ?? item.due_date,
        status,
        liability_state: status === "upcoming" ? ((body.due_date as string | undefined) ?? item.due_date) < TODAY ? "overdue" : "upcoming" : status,
        version,
      };
      this.obligations[index] = next;
      for (const other of this.obligations) other.version = version;
    }
    const current = this.obligations[index] as Obligation;
    return { status: 200, body: { commitment: current, sources: [this.source(current.id, "bill_due", current.amount_minor)], version: current.version } };
  }

  // ── Records ────────────────────────────────────────────────────────────────
  private page(query: URLSearchParams): FakeResponse {
    const limit = Number(query.get("limit") ?? 50);
    const offset = Number(query.get("offset") ?? 0);
    if (!Number.isInteger(limit) || limit < 1 || limit > 200 || !Number.isInteger(offset) || offset < 0) return envelope(422, "validation_error");
    const pinned = query.get("data_version");
    if (pinned && pinned !== String(this.version)) return envelope(409, "version_conflict");
    const scope = query.get("scope") ?? "month";
    const dataset = query.get("dataset") === "quarantined" ? "quarantined" : "household";
    let rows = this.transactions.filter((item) => item.dataset === dataset);
    if (scope === "unresolved") rows = rows.filter((item) => item.status === "needs_review");
    else if (query.get("status")) rows = rows.filter((item) => item.status === query.get("status"));
    const month = query.get("period") === "month" ? Number(query.get("month")) : scope === "month" ? 10 : null;
    if (month !== null && (scope === "month" || query.get("period") === "month")) rows = rows.filter((item) => Number(item.occurred_at.slice(5, 7)) === month);
    for (const key of ["category", "kind"] as const) if (query.get(key)) rows = rows.filter((item) => item[key] === query.get(key));
    if (query.get("source")) rows = rows.filter((item) => item.source_modes.includes(query.get("source") as "gmail"));
    const q = query.get("q")?.toLowerCase();
    if (q) rows = rows.filter((item) => item.merchant.toLowerCase().includes(q));
    rows.sort((a, b) => b.occurred_at.localeCompare(a.occurred_at) || a.id.localeCompare(b.id));
    const items = rows.slice(offset, offset + limit).map((item) => ({ ...item, version: String(this.version) }));
    return {
      status: 200,
      body: { items, total: rows.length, unresolved_total: this.unresolved.length, limit, offset, next_offset: offset + limit < rows.length ? offset + limit : null, data_version: String(this.version), dataset },
    };
  }

  private source(id: string, eventType: string, amount: number) {
    return {
      id: uuid("80000000", parseInt(id.slice(-4), 16)),
      email_source_id: uuid("81000000", parseInt(id.slice(-4), 16)),
      source: "gmail",
      sender_domain: "alerts.example.test",
      received_at: "2026-10-21T19:06:00+05:30",
      classification: "transaction_alert",
      event_type: eventType,
      amount_minor: amount,
      currency: "INR",
      merchant: "Sample Books",
      occurred_at: "2026-10-21T19:05:00+05:30",
      due_date: null,
      extraction_method: "rule",
      extractor_id: "rules.synthetic",
      evidence: { amount_minor: "INR 799.00 spent", merchant: "at SAMPLE BOOKS" },
      field_confidence: { amount_minor: 1 },
    };
  }

  private detail(item: Tx) {
    return {
      transaction: { ...item, version: String(this.version) },
      sources: [this.source(item.id, "debit", item.amount_minor)],
      confidence_factors: { trusted_sender_template: 0.25, deterministic_amount_date: 0.25, unique_reference: 0, cross_source_agreement: null, merchant_category_quality: 0.15, source_count: item.source_count },
      revisions: [],
      version: String(this.version),
      decisions: (this.decisions.get(item.id) ?? []).map(({ id, action, created_at, undone_at }) => ({
        id,
        action,
        created_at,
        undone_at,
        can_undo: undone_at === null && this.lastDecision()?.id === id,
      })),
    };
  }

  private lastDecision(): Decision | undefined {
    return [...this.decisions.values()].flat().sort((a, b) => Number(b.after) - Number(a.after))[0];
  }

  private candidates(id: string): FakeResponse {
    const item = this.transactions.find((row) => row.id === id);
    if (!item) return envelope(404, "not_found");
    const items = this.transactions.filter(
      (row) => row.id !== id && row.dataset === "household" && row.direction === item.direction && ["confirmed", "needs_review"].includes(row.status) && Math.abs(row.amount_minor - item.amount_minor) <= 100,
    );
    return { status: 200, body: { items: items.map((row) => ({ ...row, version: String(this.version) })), suggested_id: item.possible_duplicate_of_id, data_version: String(this.version) } };
  }

  private preview(id: string, body: Json): FakeResponse {
    const item = this.transactions.find((row) => row.id === id);
    if (!item) return envelope(404, "not_found");
    if (body.expected_version !== String(this.version)) return envelope(409, "version_conflict");
    const before = this.summary();
    return {
      status: 200,
      body: { version: String(this.version), action: body.action, transaction_id: id, keep_id: body.keep_id ?? null, source_count: item.source_count, affected_transaction_ids: [id, body.keep_id].filter(Boolean), before_summary: before, after_summary: before },
    };
  }

  private decide(id: string, body: Json): FakeResponse {
    const index = this.transactions.findIndex((row) => row.id === id);
    const item = this.transactions[index];
    if (!item) return envelope(404, "not_found");
    if (body.expected_version !== String(this.version)) return envelope(409, "decision_conflict");
    const action = String(body.action);
    const correction = (body.correction ?? {}) as Partial<Tx>;
    const before = { ...item };
    const others: Tx[] = [];
    let next: Tx = { ...item, ...correction };
    if (action === "confirm") next = { ...next, status: "confirmed", review_reason: null };
    else if (action === "reject") next = { ...next, status: "rejected", review_reason: null };
    else if (action === "reopen") next = { ...next, status: "needs_review", review_reason: item.review_reason ?? "low_confidence" };
    else if (action === "keep-separate") next = { ...next, status: "confirmed", review_reason: null, possible_duplicate_of_id: null };
    else if (action === "merge") {
      const target = this.transactions.find((row) => row.id === body.keep_id);
      if (!target) return envelope(422, "validation_error");
      others.push({ ...target });
      Object.assign(target, { source_count: target.source_count + item.source_count });
      next = { ...next, status: "merged", merged_into_id: target.id, review_reason: null };
    } else if (action !== "correct") return envelope(422, "validation_error");
    this.transactions[index] = next;
    const version = this.bump();
    const decision: Decision = { id: uuid("90000000", this.counter++), action, created_at: NOW, undone_at: null, can_undo: true, before, after: version, others };
    this.decisions.set(id, [decision, ...(this.decisions.get(id) ?? [])]);
    return { status: 200, body: { detail: this.detail(next), decision_id: decision.id, data_version: version } };
  }

  private undo(id: string, decisionId: string, body: Json): FakeResponse {
    const decision = (this.decisions.get(id) ?? []).find((item) => item.id === decisionId);
    if (!decision) return envelope(404, "not_found");
    if (decision.undone_at || body.expected_version !== String(this.version) || decision.after !== String(this.version)) return envelope(409, "decision_conflict");
    const index = this.transactions.findIndex((row) => row.id === id);
    this.transactions[index] = decision.before;
    for (const other of decision.others) {
      const at = this.transactions.findIndex((row) => row.id === other.id);
      if (at >= 0) this.transactions[at] = other;
    }
    decision.undone_at = NOW;
    const version = this.bump();
    return { status: 200, body: { detail: this.detail(decision.before), decision_id: decision.id, data_version: version } };
  }

  // ── Imports ────────────────────────────────────────────────────────────────
  private importRoute(id: string, action: string | null, body: Json): FakeResponse {
    const run = this.imports.get(id);
    if (!run) return envelope(404, "not_found");
    if (action === null) {
      if (id === ids.runningImport && run.outcome === "running") {
        this.polls += 1;
        const processed = Math.min(15, 3 + this.polls * 4);
        Object.assign(run, { emails_processed: processed });
        if (processed >= 15) Object.assign(run, { status: "completed", outcome: "complete", transactions_created: 4, needs_review: 4, non_financial_skipped: 9, finished_at: NOW });
      }
      return { status: 200, body: { ...run, data_version: String(this.version) } };
    }
    if (action === "issues") {
      const count = Number(run.failed ?? 0);
      const items = Array.from({ length: count }, (_, index) => ({
        id: uuid("20000000", index + 1),
        source_id: uuid("21000000", index + 1),
        source_mode: run.mode,
        reason: index === 0 ? "extraction_failed" : "no_supported_events",
        retryable: true,
        retry_strategy: run.mode === "eml_upload" ? "select_original_files" : "refetch_gmail",
        attempts: 1,
      }));
      return { status: 200, body: { items, total: items.length, next_offset: null } };
    }
    if (body.expected_version !== String(this.version)) return envelope(409, "version_conflict");
    if (action === "retry") {
      if (run.mode === "eml_upload") return envelope(409, "original_files_required");
      this.polls = 0;
      const retryId = uuid("30000000", this.counter++);
      this.imports.set(retryId, { ...run, id: retryId, failed: 0, outcome: "complete", status: "completed", transactions_created: 2, needs_review: 2, started_at: NOW, data_version: this.bump() });
      return { status: 202, body: { import_run_id: retryId } };
    }
    if (action === "cancel") {
      Object.assign(run, { cancel_requested: true });
      return { status: 200, body: { ...run, data_version: String(this.version) } };
    }
    if (action === "continue") return envelope(422, "invalid_decision");
    return envelope(404, "not_found");
  }

  // ── Assistant ──────────────────────────────────────────────────────────────
  private ask(body: Json): FakeResponse {
    const text = String(body.text ?? "");
    if (text.includes("unavailable")) return envelope(503, "provider_unavailable");
    const style = String(body.display_style ?? "auto");
    const romanized = style === "hinglish" || style === "manglish";
    const language = style === "hi" || style === "hinglish" ? "hi" : style === "ml" || style === "manglish" ? "ml" : "en";
    const evidence = this.transactions.filter((item) => item.merchant === "Sample Books" && item.status === "confirmed");
    const labels: Record<string, Record<string, string>> = {
      en: { spent: "Spent at Sample Books", refunds: "Refunds", warning: "Some records still need review" },
      hi: { spent: romanized ? "Sample Books par kharch" : "Sample Books पर खर्च", refunds: romanized ? "Refund" : "रिफ़ंड", warning: romanized ? "Kuch records review baaki hain" : "कुछ रिकॉर्ड की समीक्षा बाकी है" },
      ml: { spent: romanized ? "Sample Books-il chelavu" : "Sample Books-ൽ ചെലവ്", refunds: romanized ? "Refund" : "റീഫണ്ട്", warning: romanized ? "Chila records review cheyyanund" : "ചില രേഖകൾ പരിശോധിക്കാനുണ്ട്" },
    };
    const label = labels[language] as Record<string, string>;
    return {
      status: 200,
      body: {
        intent: "merchant_total",
        policy: "answer",
        display_text: language === "en" ? "You spent ₹799 at Sample Books this month, with a ₹200 refund — ₹599 net." : `${label.spent}: ₹599`,
        speech_text: "Synthetic spoken answer.",
        speech_language: language,
        display_language: language,
        display_script: language === "en" || romanized ? "Latn" : language === "hi" ? "Deva" : "Mlym",
        facts: [
          { key: "merchant_outgoing", label: label.spent, amount_minor: 79900, count: null, currency: "INR" },
          { key: "merchant_refunds", label: label.refunds, amount_minor: 20000, count: null, currency: "INR" },
        ],
        simulation: null,
        evidence_transactions: evidence,
        evidence_total: 3,
        evidence_sampled: true,
        warnings: ["pending_review_items"],
        warning_labels: { pending_review_items: label.warning },
        data_version: String(this.version),
        dataset: "household",
        resolved_period: { start: "2026-10-01", end: "2026-10-31", label: language === "en" ? "October 2026" : "अक्टूबर 2026" },
      },
    };
  }

  private speak(): FakeResponse {
    // A generated 0.6 s sine tone (ffmpeg lavfi), not provider speech: it proves the UI's
    // playback states in a browser, never real voice quality or phone playback.
    return { status: 200, headers: { "content-type": "audio/mpeg" }, raw: readFileSync(new URL("../fixtures/synthetic-tone.mp3", import.meta.url)) };
  }

  // ── Sample (demo) ──────────────────────────────────────────────────────────
  private demo() {
    const sample = (row: Tx) => ({ ...row, id: row.id.replace(/^10000000/, "d0000000"), dataset: "demo" });
    const summary = { ...this.summary(), dataset: "demo", data_version: "demo-1" };
    return {
      dataset: "demo",
      read_only: true,
      as_of: "2026-10-28",
      summary,
      transactions: this.transactions.filter((row) => row.dataset === "household").slice(0, 8).map(sample),
      commitments: this.obligations.map((row) => ({ ...row, id: row.id.replace(/^50000000/, "d5000000"), dataset: "demo" })),
    };
  }
}
