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
  source_modes: ("gmail" | "eml_upload" | "whatsapp_image" | "whatsapp_voice" | "manual_entry" | "gpay_statement")[];
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
const BUDGETED = [
  "total", "rent", "food_dining", "groceries", "transport", "shopping", "utilities", "subscriptions", "travel", "health",
  "education", "investments", "loan_emi", "fees", "farming", "livestock", "phone_recharge", "family_events", "remittance", "other",
];
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
  /** Sign-up round: "Continue with WhatsApp" is offered (Google's script is never loaded in tests). */
  whatsapp?: boolean;
  signupOpen?: boolean;
  /** The signed-in household joined by itself (so it can delete its account). */
  selfServe?: boolean;
  /** Statement round: Google Pay statements can be imported (STATEMENT_IMPORT_ENABLED). */
  statementImport?: boolean;
};

/** One synthetic statement row: invented payees, a made-up bank and UPI IDs. */
type StatementRow = { name: string; rupees: number; day: string; direction?: Direction; category?: string };
// Apr–Sep 2026: a card bill and broadband paid every month, tea several times a week, money
// lent to a friend and mostly paid back, and one payment the household had already spoken.
const STATEMENT_ROWS: StatementRow[] = [
  { name: "Asha Stores", rupees: 2840, day: "2026-04-01" },
  { name: "Ravi Kumar", rupees: 12400, day: "2026-05-01" },
  { name: "Asha Stores", rupees: 1150, day: "2026-05-03" },
  { name: "Ravi Kumar", rupees: 12320, day: "2026-05-09", direction: "in" },
  { name: "Asha Stores", rupees: 3960, day: "2026-06-03" },
  ...["06", "07", "08", "09"].map((month) => ({ name: "Sample Broadband", rupees: 749.5, day: `2026-${month}-05`, category: "utilities" })),
  ...["07", "08", "09"].flatMap((month) => ["02", "09", "16"].map((day) => ({ name: "Corner Tea", rupees: 12, day: `2026-${month}-${day}` }))),
  { name: "Meera Nair", rupees: 2000, day: "2026-07-15", direction: "in" },
  { name: "Sample Card", rupees: 4810, day: "2026-07-20" },
  { name: "Big Electronics", rupees: 9720, day: "2026-08-09", category: "shopping" },
  { name: "Sample Card", rupees: 4830, day: "2026-08-20" },
  { name: "Sample Dairy", rupees: 500, day: "2026-09-03", category: "groceries" },
  { name: "Sample Card", rupees: 4865, day: "2026-09-20" },
];
const isSpending = (item: Tx) => item.direction === "out" && item.kind !== "transfer";
const isIncome = (item: Tx) => item.direction === "in" && ["salary", "income_other"].includes(item.kind);
// Payees and searches ignore spaces, as the API does: Google Pay prints some names both ways.
const payeeKey = (name: string) => name.toLowerCase().replace(/\s+/g, "");
const share = (part: number, whole: number) => (whole ? Math.round((part / whole) * 10_000) / 10_000 : 0);
const lastDay = (year: number, month: number) => new Date(Date.UTC(year, month, 0)).getUTCDate();
function groupByPayee(rows: Tx[]) {
  const groups = new Map<string, Tx[]>();
  for (const row of rows) groups.set(payeeKey(row.merchant), [...(groups.get(payeeKey(row.merchant)) ?? []), row]);
  return [...groups.values()];
}
const amountOf = (rows: Tx[]) => rows.reduce((sum, row) => sum + row.amount_minor, 0);

export const LOGIN_CODE = "K7Q2-9FXM";

export class FakeFinBoyApi {
  version = 100;
  authRequired: boolean;
  signedIn: boolean;
  transactions: Tx[] = [];
  decisions = new Map<string, Decision[]>();
  obligations: Obligation[] = [];
  imports = new Map<string, ImportRun>();
  // Monthly limits by category ("total" is all spending) and the savings goal (money manager).
  budgets = new Map<string, number>([["food_dining", 300000]]);
  goal: number | null = null;
  connection: Json | null;
  failures: { pattern: RegExp; method: string | null; response: FakeResponse; times: number }[] = [];
  delays: { pattern: RegExp; ms: number }[] = [];
  outcomes: string[] = [];
  requests: { method: string; path: string; body: unknown }[] = [];
  whatsapp: boolean;
  signupOpen: boolean;
  selfServe: boolean;
  login: { state: "pending" | "confirmed" | "declined" | "used"; purpose: string } | null = null;
  statementImport: boolean;
  /** What the next uploaded statement turns out to be; errors use failNext on /imports/gpay. */
  statementOutcome: "imported" | "mismatch" = "imported";
  private statements = new Map<string, { rows: Tx[]; polls: number }>();
  private polls = 0;
  private counter = 900;

  constructor(scenario: Scenario = {}) {
    this.authRequired = scenario.authRequired ?? true;
    this.signedIn = scenario.signedIn ?? true;
    this.whatsapp = scenario.whatsapp ?? false;
    this.signupOpen = scenario.signupOpen ?? true;
    this.selfServe = scenario.selfServe ?? false;
    this.statementImport = scenario.statementImport ?? false;
    const status = scenario.connection ?? "active";
    this.connection =
      status === "none"
        ? null
        : { id: ids.connection, provider: "gmail", account_email_masked: "ho***@example.test", status, last_synced_at: "2026-10-24T09:00:00+05:30" };
    if (!scenario.emptyLedger) this.seed(scenario.bulk ?? 0);
    // Said on WhatsApp before the statement arrived: the statement's own row waits for review.
    if (this.statementImport && !scenario.emptyLedger) {
      this.transactions.push(tx(13, { merchant: "Milk", amount_minor: 50000, category: "groceries", occurred_at: "2026-09-03T08:00:00+05:30", source_modes: ["whatsapp_voice"], payment_verification: "unverified" }));
    }
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
  /** What tapping ✅ or ❌ on the WhatsApp card does to a pending sign-in. */
  answerWhatsApp(choice: "yes" | "no") {
    if (this.login?.state === "pending") this.login.state = choice === "yes" ? "confirmed" : "declined";
  }
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
  /** A statement already imported and saved, as if uploaded earlier; returns its import run. */
  seedStatement() {
    const id = this.startStatement();
    const run = this.imports.get(id) as ImportRun;
    while (run.outcome === "running") this.statementRoute(id, run, null, {});
    return id;
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
    const open = [
      "/api/v1/health",
      "/api/v1/auth/session",
      "/api/v1/auth/login",
      "/api/v1/auth/whatsapp/start",
      "/api/v1/auth/whatsapp/status",
      "/api/v1/auth/whatsapp/complete",
      "/api/v1/demo",
    ].includes(path);
    if (this.authRequired && !open && !this.signedIn) return envelope(401, "authentication_required");
    if (["POST", "PATCH", "DELETE"].includes(method) && request.origin !== appOrigin) return envelope(403, "origin_not_allowed");
    return this.route(method, path, query, (body ?? {}) as Json);
  }

  private route(method: string, path: string, query: URLSearchParams, body: Json): FakeResponse {
    const ok = (value: unknown, status = 200): FakeResponse => ({ status, body: value });
    let match: RegExpMatchArray | null;
    if (path === "/api/v1/health") return ok({ service: "finboy-api", version: "0.1.0", status: "ok", database: "connected" });
    if (path === "/api/v1/auth/session") {
      const authenticated = !this.authRequired || this.signedIn;
      return ok({
        authenticated,
        required: this.authRequired,
        household: authenticated
          ? this.selfServe
            ? { owner: false, joined_via: "whatsapp", whatsapp: "•••• 0071", google: null }
            : { owner: true, joined_via: null, whatsapp: null, google: null }
          : null,
        sign_in: {
          whatsapp: this.whatsapp,
          whatsapp_number: this.whatsapp ? "919000000099" : null,
          google_client_id: null,
          password: this.authRequired,
          signup_open: this.signupOpen,
          gmail: !this.selfServe,
        },
        statement_import: this.statementImport,
      });
    }
    if (path === "/api/v1/auth/whatsapp/start" && method === "POST" && this.whatsapp) {
      this.login = { state: "pending", purpose: String(body.purpose ?? "sign_in") };
      return ok({
        code: LOGIN_CODE,
        link: `https://wa.me/919000000099?text=FinBoy%20login%20code%20${LOGIN_CODE}`,
        expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
      });
    }
    if (path === "/api/v1/auth/whatsapp/status") {
      return ok({ state: this.login?.state ?? "expired", signup_open: this.signupOpen });
    }
    if (path === "/api/v1/auth/whatsapp/complete" && method === "POST") {
      if (this.login?.state !== "confirmed") return envelope(410, "login_expired");
      this.login.state = "used";
      this.signedIn = true;
      return ok({ authenticated: true });
    }
    if (path === "/api/v1/auth/logout-everywhere" && method === "POST") {
      this.signedIn = false;
      return ok({ authenticated: false });
    }
    if (path === "/api/v1/account/delete" && method === "POST") {
      if (!this.selfServe) return envelope(403, "owner_household");
      this.signedIn = false;
      this.transactions = [];
      this.obligations = [];
      return ok({ deleted: true });
    }
    if (path === "/api/v1/entries/preview" && method === "POST") return ok(this.readEntry(String(body.text ?? "")));
    if (path === "/api/v1/entries" && method === "POST") return ok(this.saveEntry(body));
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
    if (path === "/api/v1/money/insights") return ok(this.insights(query));
    if (path === "/api/v1/money/payees") return ok(this.payees(query));
    if (path === "/api/v1/money/payees/category" && method === "POST") return this.sortPayee(body);
    if (path === "/api/v1/money/budgets") return this.budgetRoute(method, body, query);
    if (path === "/api/v1/money/goal" && method === "PATCH") {
      const goal = body.goal_minor;
      if (goal !== null && (typeof goal !== "number" || !Number.isInteger(goal) || goal <= 0)) return envelope(422, "invalid_request");
      this.goal = goal as number | null;
      return ok(this.budgetPlan(null));
    }
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
    if (path === "/api/v1/imports/gpay" && method === "POST") {
      if (!this.statementImport) return envelope(404, "statement_import_off");
      return ok({ import_run_id: this.startStatement() }, 202);
    }
    if ((match = path.match(/^\/api\/v1\/imports\/([^/]+)(?:\/(issues|retry|cancel|continue|removal-preview|remove))?$/))) return this.importRoute(match[1] ?? "", match[2] ?? null, body);
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
  budgetRoute(method: string, body: Json, query: URLSearchParams): FakeResponse {
    if (method === "GET") return { status: 200, body: this.budgetPlan(query) };
    const category = String(body.category);
    const limit = body.limit_minor;
    if (method !== "PATCH" || !BUDGETED.includes(category)) return envelope(422, "invalid_request");
    if (limit === null) this.budgets.delete(category);
    else if (typeof limit === "number" && Number.isInteger(limit) && limit > 0) this.budgets.set(category, limit);
    else return envelope(422, "invalid_request");
    return { status: 200, body: this.budgetPlan(null) };
  }

  budgetPlan(query: URLSearchParams | null) {
    const summary = this.summary(query);
    const spent = new Map(summary.categories.map((item) => [item.category, item.amount_minor]));
    const kept = Math.max(0, spent.get("investments") ?? 0);
    const items = [...this.budgets.entries()].map(([category, limit]) => {
      const used = category === "total" ? summary.confirmed_outflows_minor : Math.max(0, spent.get(category) ?? 0);
      return { category, limit_minor: limit, spent_minor: used, level: used > limit ? "over" : used * 5 >= limit * 4 ? "near" : "ok" };
    });
    items.sort((a, b) => Number(a.category !== "total") - Number(b.category !== "total") || b.spent_minor / b.limit_minor - a.spent_minor / a.limit_minor);
    return {
      period_start: summary.period_start,
      period_end: summary.period_end,
      as_of: summary.as_of,
      income_minor: summary.tracked_income_minor,
      spent_minor: summary.confirmed_outflows_minor,
      saved_minor: summary.tracked_income_minor - summary.confirmed_outflows_minor + kept,
      goal_minor: this.goal,
      items,
      categories: BUDGETED,
    };
  }

  /** The query's days: a month (this one, October, by default) or `period=range` start–end. */
  periodOf(query: URLSearchParams | null) {
    if (query?.get("period") === "range") {
      const start = query.get("start") ?? TODAY;
      const end = query.get("end") ?? TODAY;
      return { start, end, includes: (item: Tx) => item.occurred_at.slice(0, 10) >= start && item.occurred_at.slice(0, 10) <= end };
    }
    const month = query?.get("period") === "month" ? Number(query.get("month")) : 10;
    const mm = String(month).padStart(2, "0");
    return {
      start: `2026-${mm}-01`,
      end: `2026-${mm}-${lastDay(2026, month)}`,
      includes: (item: Tx) => Number(item.occurred_at.slice(5, 7)) === month,
    };
  }

  summary(query: URLSearchParams | null = null) {
    const period = this.periodOf(query);
    const inMonth = (item: Tx) => period.includes(item) && item.dataset === "household";
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
      period_start: period.start,
      period_end: period.end,
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

  /** A small mirror of services/money/insights.py over the confirmed records. */
  insights(query: URLSearchParams | null) {
    const period = this.periodOf(query);
    const confirmed = this.transactions.filter((item) => item.status === "confirmed" && item.dataset === "household");
    const entries = confirmed.filter(period.includes);
    const out = entries.filter(isSpending);
    const got = entries.filter(isIncome);
    const moneyOut = amountOf(out);
    const months = (Number(period.end.slice(0, 4)) - Number(period.start.slice(0, 4))) * 12 + Number(period.end.slice(5, 7)) - Number(period.start.slice(5, 7)) + 1;
    const payees = (rows: Tx[], whole: number, limit: number) =>
      groupByPayee(rows)
        .sort((a, b) => amountOf(b) - amountOf(a))
        .slice(0, limit)
        .map((items) => ({ name: items[0]?.merchant ?? "", amount_minor: amountOf(items), count: items.length, share: share(amountOf(items), whole), category: items[0]?.category ?? "other" }));
    // Regular: a steady amount (±10%) in 3+ of the six months ending with the period, at most twice a
    // month, and not over ten days late by the last record in the window.
    const endMonth = Number(period.end.slice(0, 4)) * 12 + Number(period.end.slice(5, 7)) - 1;
    const monthIndex = (item: Tx) => Number(item.occurred_at.slice(0, 4)) * 12 + Number(item.occurred_at.slice(5, 7)) - 1;
    const window = confirmed.filter((item) => isSpending(item) && endMonth - monthIndex(item) < 6 && monthIndex(item) <= endMonth);
    const latest = window.map((item) => item.occurred_at.slice(0, 10)).sort().at(-1) ?? TODAY;
    const regular = groupByPayee(window).flatMap((items) => {
      let best: { months: number; near: Tx[] } | null = null;
      for (const usual of [...new Set(items.map((item) => item.amount_minor))].sort((a, b) => a - b)) {
        const near = items.filter((item) => Math.abs(item.amount_minor - usual) <= usual * 0.1);
        const seen = new Set(near.map(monthIndex)).size;
        if (seen < 3 || near.length > 2 * seen) continue;
        if (!best || seen > best.months || (seen === best.months && near.length >= best.near.length)) best = { months: seen, near };
      }
      if (!best) return [];
      const amounts = best.near.map((item) => item.amount_minor).sort((a, b) => a - b);
      const last = best.near.map((item) => item.occurred_at.slice(0, 10)).sort().at(-1) ?? TODAY;
      const [year, month, day] = last.split("-").map(Number) as [number, number, number];
      const next = month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 };
      const expected = `${next.year}-${String(next.month).padStart(2, "0")}-${String(Math.min(day, lastDay(next.year, next.month))).padStart(2, "0")}`;
      if (Date.parse(latest) - Date.parse(expected) > 10 * 86_400_000) return [];
      return [{
        name: items[0]?.merchant ?? "",
        usual_minor: amounts[Math.floor((amounts.length - 1) / 2)] ?? 0,
        months: best.months,
        last_paid: last,
        next_expected: expected,
        category: best.near[0]?.category ?? "other",
      }];
    }).sort((a, b) => b.usual_minor - a.usual_minor);
    const sent = new Map(groupByPayee(out).map((items) => [payeeKey(items[0]?.merchant ?? ""), items]));
    const people = groupByPayee(got)
      .filter((items) => sent.has(payeeKey(items[0]?.merchant ?? "")))
      .map((back) => {
        const went = sent.get(payeeKey(back[0]?.merchant ?? "")) ?? [];
        const all = [...went, ...back];
        return {
          name: went[0]?.merchant ?? "",
          sent_minor: amountOf(went),
          received_minor: amountOf(back),
          balance_minor: amountOf(back) - amountOf(went),
          count: all.length,
          last_on: all.map((item) => item.occurred_at.slice(0, 10)).sort().at(-1) ?? TODAY,
        };
      });
    const small = out.filter((item) => item.amount_minor < 20_000);
    return {
      period_start: period.start,
      period_end: period.end,
      months,
      money_out_minor: moneyOut,
      money_in_minor: amountOf(got),
      payment_count: out.length,
      top_payees: payees(out, moneyOut, 8),
      top_senders: payees(got, amountOf(got), 5),
      biggest: [...out]
        .sort((a, b) => b.amount_minor - a.amount_minor || a.occurred_at.localeCompare(b.occurred_at))
        .slice(0, 5)
        .map((item) => ({ id: item.id, name: item.merchant, amount_minor: item.amount_minor, occurred_at: item.occurred_at, category: item.category })),
      regular: regular.slice(0, 8),
      regular_monthly_minor: regular.reduce((sum, item) => sum + item.usual_minor, 0),
      people,
      small: {
        threshold_minor: 20_000,
        count: small.length,
        amount_minor: amountOf(small),
        per_month_minor: Math.floor(amountOf(small) / months),
        count_share: share(small.length, out.length),
        amount_share: share(amountOf(small), moneyOut),
        places: groupByPayee(small)
          .sort((a, b) => b.length - a.length)
          .slice(0, 3)
          .map((items) => ({ name: items[0]?.merchant ?? "", amount_minor: amountOf(items), count: items.length, share: share(items.length, small.length), category: items[0]?.category ?? "other" })),
      },
      data_version: String(this.version),
    };
  }

  /** Spending payees still under "Other" in the period, largest first. */
  payees(query: URLSearchParams | null) {
    const period = this.periodOf(query);
    const out = this.transactions.filter((item) => item.status === "confirmed" && item.dataset === "household" && isSpending(item) && period.includes(item));
    const unsorted = out.filter((item) => item.category === "other");
    return {
      items: groupByPayee(unsorted)
        .sort((a, b) => amountOf(b) - amountOf(a))
        .map((items) => ({ name: items[0]?.merchant ?? "", count: items.length, amount_minor: amountOf(items) })),
      spent_minor: amountOf(out),
      unsorted_minor: amountOf(unsorted),
      data_version: String(this.version),
    };
  }

  private sortPayee(body: Json): FakeResponse {
    if (body.expected_version !== String(this.version)) return envelope(409, "version_conflict");
    const key = payeeKey(String(body.name ?? ""));
    const category = String(body.category);
    const rows = this.transactions.filter((item) => item.dataset === "household" && isSpending(item) && payeeKey(item.merchant) === key && item.category !== category);
    for (const row of rows) row.category = category;
    return { status: 200, body: { updated: rows.length, data_version: this.bump() } };
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
    if (query.get("period") === "range") rows = rows.filter(this.periodOf(query).includes);
    else {
      const month = query.get("period") === "month" ? Number(query.get("month")) : scope === "month" ? 10 : null;
      if (month !== null && (scope === "month" || query.get("period") === "month")) rows = rows.filter((item) => Number(item.occurred_at.slice(5, 7)) === month);
    }
    for (const key of ["category", "kind"] as const) if (query.get(key)) rows = rows.filter((item) => item[key] === query.get(key));
    if (query.get("source")) rows = rows.filter((item) => item.source_modes.includes(query.get("source") as "gmail"));
    const q = query.get("q");
    if (q) rows = rows.filter((item) => payeeKey(item.merchant).includes(payeeKey(q)));
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

  /** A statement row's evidence, as services/statements/persist.py writes it. */
  private statementSource(item: Tx) {
    const index = parseInt(item.id.slice(-4), 16);
    return {
      ...this.source(item.id, item.direction === "in" ? "credit" : "debit", item.amount_minor),
      id: uuid("82000000", index),
      email_source_id: uuid("83000000", index),
      source: "gpay_statement",
      sender_domain: "google-pay.invalid",
      received_at: item.occurred_at,
      classification: "upi_alert",
      merchant: item.merchant,
      occurred_at: item.occurred_at,
      extractor_id: "gpay-statement-v1",
      evidence: {
        payment_proof: "Google Pay statement",
        statement: "gpay",
        detail: `${item.direction === "in" ? "Received from" : "Paid to"} ${item.merchant}`,
        bank: "Sample Bank",
        page: "3",
        row: "2",
      },
      field_confidence: { amount_minor: 1, occurred_at: 1, merchant: 1, reference_id: 1 },
    };
  }

  private detail(item: Tx) {
    return {
      transaction: { ...item, version: String(this.version) },
      sources: [item.source_modes.includes("gpay_statement") ? this.statementSource(item) : this.source(item.id, "debit", item.amount_minor)],
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

  // ── Quick add ──────────────────────────────────────────────────────────────
  /** A small stand-in for the statement reader: one amount, a verb, nothing stored. */
  private readEntry(text: string) {
    const amount = text.match(/\d[\d,]*/)?.[0]?.replaceAll(",", "");
    const kind = /\?|^how|^what/i.test(text)
      ? "question"
      : /due|fees/i.test(text)
        ? "due"
        : /got|received|salary|കിട്ടി/i.test(text)
          ? "received"
          : /paid|spent|gave|bought|दिए|കൊടുത്തു/i.test(text)
            ? "spent"
            : "unclear";
    const money = kind === "spent" || kind === "received" || kind === "due";
    return {
      kind,
      amount_minor: money && amount ? Number(amount) * 100 : null,
      counterparty: /milkman/i.test(text) ? "milkman" : /പാൽക്കാരന്/.test(text) ? "പാൽക്കാരന്" : null,
      category: /milk|പാൽ/i.test(text) ? "groceries" : kind === "due" ? "education" : "other",
      day: money && kind !== "due" ? TODAY : null,
      due_date: kind === "due" ? "2026-11-10" : null,
      label: kind === "due" ? "School fees" : null,
    };
  }

  private saveEntry(body: Json) {
    const version = this.bump();
    if (body.kind === "due") {
      const id = uuid("70000000", this.counter++);
      this.obligations.push({
        ...this.obligations[0],
        id,
        kind: "bill",
        label: String(body.label ?? "Payment"),
        amount_minor: Number(body.amount_minor),
        due_date: String(body.due_date),
        status: "upcoming",
        liability_state: "upcoming",
        uncertain: false,
        version,
      } as Obligation);
      return { kind: "due", transaction_id: null, decision_id: null, obligation_id: id, data_version: version };
    }
    const row = tx(this.counter++, {
      direction: body.kind === "received" ? "in" : "out",
      kind: body.kind === "received" ? "income_other" : "purchase",
      amount_minor: Number(body.amount_minor),
      merchant: String(body.counterparty ?? (body.kind === "received" ? "Money in" : "Money out")),
      category: String(body.category ?? "other"),
      occurred_at: `${String(body.day ?? TODAY)}T12:00:00+05:30`,
      status: "confirmed",
      source_modes: ["manual_entry"],
    });
    this.transactions.unshift(row);
    const decision: Decision = {
      id: uuid("90000000", this.counter++),
      action: "confirm",
      created_at: NOW,
      undone_at: null,
      can_undo: true,
      before: { ...row, status: "needs_review", review_reason: "unverified_payment" },
      after: version,
      others: [],
    };
    this.decisions.set(row.id, [decision]);
    return { kind: "record", transaction_id: row.id, decision_id: decision.id, obligation_id: null, data_version: version };
  }

  // ── Imports ────────────────────────────────────────────────────────────────
  /** A checked statement saves on the third poll; one that doesn't add up fails at once. */
  private startStatement(): string {
    const id = uuid("30000000", this.counter++);
    const reconciled = this.statementOutcome === "imported";
    const rows = STATEMENT_ROWS.map((row, index) => {
      const direction = row.direction ?? "out";
      const amount = Math.round(row.rupees * 100);
      const occurred = `${row.day}T19:${String(index % 60).padStart(2, "0")}:00+05:30`;
      const spoken = this.transactions.find(
        (item) =>
          item.source_modes.includes("whatsapp_voice") &&
          item.status === "confirmed" &&
          item.direction === direction &&
          item.amount_minor === amount &&
          Math.abs(Date.parse(item.occurred_at) - Date.parse(occurred)) <= 36 * 3_600_000,
      );
      return tx(this.counter++, {
        direction,
        kind: direction === "in" ? "income_other" : "purchase",
        amount_minor: amount,
        merchant: row.name,
        category: row.category ?? (direction === "in" ? "other_income" : "other"),
        occurred_at: occurred,
        status: spoken ? "needs_review" : "confirmed",
        review_reason: spoken ? "possible_duplicate" : null,
        possible_duplicate_of_id: spoken?.id ?? null,
        confidence: 1,
        reference_id: `${row.day.replaceAll("-", "").slice(2)}${String(index + 1).padStart(6, "0")}`,
        payment_instrument: "UPI",
        account_last4: "1234",
        source_modes: ["gpay_statement"],
      });
    });
    const paid = amountOf(rows.filter((row) => row.direction === "out"));
    const got = amountOf(rows.filter((row) => row.direction === "in"));
    this.imports.set(id, {
      id,
      mode: "gpay_statement",
      status: reconciled ? "running" : "failed",
      headers_checked: rows.length,
      candidates_found: rows.length,
      emails_processed: 0,
      events_extracted: 0,
      transactions_created: 0,
      duplicates_merged: 0,
      needs_review: 0,
      non_financial_skipped: 0,
      failed: 0,
      error_code: reconciled ? null : "extraction_failed",
      started_at: NOW,
      finished_at: reconciled ? null : NOW,
      outcome: reconciled ? "running" : "failed",
      retryable: false,
      retry_strategy: "none",
      cancel_requested: false,
      window_start: "2026-04-01",
      window_end: "2026-09-30",
      truncated: false,
      data_version: this.bump(),
      can_continue: false,
      statement: {
        provider: "gpay",
        period_start: "2026-04-01",
        period_end: "2026-09-30",
        pages: 3,
        rows: rows.length,
        new: 0,
        linked: 0,
        possible_duplicates: 0,
        already_imported: 0,
        not_counted: 0,
        // Google's own totals; a statement that doesn't add up was missing a ₹12,500 row.
        sent_minor: reconciled ? paid : paid + 1_250_000,
        received_minor: got,
        paid_minor: paid,
        got_minor: got,
        reconciled,
        accounts: ["Sample Bank ••1234"],
        holder_matches: null,
        removed_at: null,
      },
    });
    // Two polls of saving (about three seconds) keep the saving state on screen long enough to see.
    if (reconciled) this.statements.set(id, { rows, polls: 2 });
    return id;
  }

  private statementRoute(id: string, run: ImportRun, action: string | null, body: Json): FakeResponse | null {
    const saved = this.statements.get(id);
    const statement = run.statement as Json;
    if (action === null && saved && run.outcome === "running") {
      if (saved.polls > 0) saved.polls -= 1;
      else {
        this.transactions.push(...saved.rows);
        const added = saved.rows.filter((row) => row.status === "confirmed").length;
        const check = saved.rows.length - added;
        Object.assign(run, { status: "completed", outcome: "complete", finished_at: NOW, emails_processed: saved.rows.length, events_extracted: saved.rows.length, transactions_created: saved.rows.length, needs_review: check });
        Object.assign(statement, { new: added, possible_duplicates: check });
        this.bump();
      }
      return null;
    }
    if (action !== "removal-preview" && action !== "remove") return null;
    if (!saved) return envelope(404, "not_found");
    if (run.status !== "completed" || statement.removed_at) return envelope(409, "invalid_decision");
    const kept = new Set(saved.rows.map((row) => row.id));
    const present = this.transactions.filter((row) => kept.has(row.id));
    if (action === "removal-preview") return { status: 200, body: { records_removed: present.length, records_kept: 0, data_version: String(this.version) } };
    if (body.expected_version !== String(this.version)) return envelope(409, "version_conflict");
    this.transactions = this.transactions.filter((row) => !kept.has(row.id));
    statement.removed_at = NOW;
    return { status: 200, body: { ...run, data_version: this.bump() } };
  }

  private importRoute(id: string, action: string | null, body: Json): FakeResponse {
    const run = this.imports.get(id);
    if (!run) return envelope(404, "not_found");
    if (run.mode === "gpay_statement") {
      const handled = this.statementRoute(id, run, action, body);
      if (handled) return handled;
    }
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
        resolved_period: { start: "2026-10-01", end: "2026-10-31", label: "2026-10-01 – 2026-10-31" },
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
