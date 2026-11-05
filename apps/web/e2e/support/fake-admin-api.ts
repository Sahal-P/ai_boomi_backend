/**
 * TEST-ONLY in-memory double of the admin API (docs/admin-round/contract.md). Synthetic data
 * only: invented households, numbers and admins. It drives browser journeys; it proves nothing
 * about the real API, which has its own unit and database tests.
 */
import type { FakeRequest, FakeResponse } from "./fake-api.ts";

type Json = Record<string, unknown>;
type Kind = "owner" | "pilot" | "self_serve" | "pending" | "former_pilot";
type Status = "active" | "suspended" | "deleted";
type Plan = "included" | "trial" | "active" | "grace" | "free";
type Action = "sign_out" | "suspend" | "restore" | "erase" | "premium" | "autopay_cancel" | "pay_link";

export type AdminScenario = {
  /** A browser that already holds an admin session. */
  signedIn?: boolean;
  /** The admin signed in with a temporary password. */
  mustChange?: boolean;
  /** Extra self-serve households, to page through. */
  bulk?: number;
};

export const ADMIN_EMAIL = "admin@example.test";
export const ADMIN_PASSWORD = "synthetic-admin-password";
export const TEMPORARY_PASSWORD = "temporary-synthetic-password";
/** The one synthetic number the double recognises (stored as a hash by the real API). */
export const PHONE = "9812345670";
const NOW = "2026-11-05T09:30:00+05:30";
const DAY = 86_400_000;
const at = (daysAgo: number) => new Date(Date.parse(NOW) - daysAgo * DAY).toISOString();
const uuid = (prefix: string, index: number) => `${prefix}-0000-4000-8000-${index.toString(16).padStart(12, "0")}`;

export const adminIds = {
  family: uuid("a1b2c3d4", 1),
  pending: uuid("b2c3d4e5", 2),
  pilot: uuid("c3d4e5f6", 3),
  paused: uuid("d4e5f6a7", 4),
  owner: "00000000-0000-0000-0000-000000000001",
  payment: uuid("60000000", 1),
  me: uuid("70000000", 1),
  colleague: uuid("70000000", 2),
};

type Household = {
  id: string;
  kind: Kind;
  status: Status;
  plan: Plan;
  renewal: "manual" | "autopay" | "off" | null;
  paidThrough: string | null;
  whatsapp: boolean;
  google: boolean;
  joined: string;
  lastActive: string | null;
  language: "en" | "hi" | "ml" | null;
  suspendedAt: string | null;
  deletedAt: string | null;
  phone: string | null;
};

const envelope = (status: number, code: string): FakeResponse => ({
  status,
  body: { error: { code, message: "The requested task could not be completed.", request_id: uuid("80000000", status) } },
});
const ok = (body: unknown): FakeResponse => ({ status: 200, body });
const short = (id: string) => id.replace(/-/g, "").slice(0, 8);
const PASSWORD_ROUTES = new Set(["/api/v1/admin/session", "/api/v1/admin/password", "/api/v1/admin/logout"]);

function allowed(house: Household): Action[] {
  if (house.kind === "owner" || house.kind === "former_pilot" || house.status === "deleted") return [];
  if (house.kind === "pending") return ["erase"];
  if (house.status === "suspended") return ["restore", "erase"];
  const actions: Action[] = ["suspend", "erase"];
  if (house.kind === "self_serve") {
    actions.unshift("sign_out");
    actions.push("premium", "pay_link");
    if (house.renewal === "autopay") actions.push("autopay_cancel");
  }
  return actions;
}

export class FakeAdminApi {
  signedIn: boolean;
  mustChange: boolean;
  households: Household[];
  payments: Json[];
  admins: Json[];
  sessions: Json[];
  audit: Json[] = [];
  stalePending = 2;

  constructor(scenario: AdminScenario = {}) {
    this.signedIn = scenario.signedIn ?? true;
    this.mustChange = scenario.mustChange ?? false;
    const house = (values: Partial<Household> & Pick<Household, "id" | "kind">): Household => ({
      status: "active",
      plan: "trial",
      renewal: null,
      paidThrough: null,
      whatsapp: true,
      google: false,
      joined: at(10),
      lastActive: at(1),
      language: "hi",
      suspendedAt: null,
      deletedAt: null,
      phone: null,
      ...values,
    });
    this.households = [
      house({ id: adminIds.family, kind: "self_serve", google: true, plan: "active", renewal: "autopay", paidThrough: at(-20), phone: `91${PHONE}` }),
      house({ id: adminIds.pending, kind: "pending", lastActive: null, language: null, joined: at(2) }),
      house({ id: adminIds.pilot, kind: "pilot", plan: "included", joined: at(40) }),
      house({ id: adminIds.paused, kind: "self_serve", status: "suspended", plan: "free", suspendedAt: at(3), joined: at(50), lastActive: at(20) }),
      house({ id: adminIds.owner, kind: "owner", plan: "included", whatsapp: true, joined: at(60), language: "en" }),
      ...Array.from({ length: scenario.bulk ?? 0 }, (_, index) =>
        house({ id: uuid("e0000000", index + 1), kind: "self_serve", joined: at(5 + (index % 20)), lastActive: at(index % 40) }),
      ),
    ];
    this.payments = [
      { id: adminIds.payment, household_id: adminIds.family, short_id: short(adminIds.family), created_at: at(0.2), amount_minor: 29900, status: "pending", kind: "checkout", mode: "UPI", txnid: "FBSYNTH0001", payu_id: null, error_code: null, covers_to: null },
      { id: uuid("60000000", 2), household_id: adminIds.family, short_id: short(adminIds.family), created_at: at(12), amount_minor: 29900, status: "paid", kind: "checkout", mode: "CC", txnid: "FBSYNTH0002", payu_id: "403993715500000002", error_code: null, covers_to: at(-20) },
    ];
    this.admins = [
      { id: adminIds.me, email: ADMIN_EMAIL, active: true, must_change_password: this.mustChange, last_login_at: at(0), created_at: at(30), you: true },
      { id: adminIds.colleague, email: "colleague@example.test", active: true, must_change_password: false, last_login_at: at(2), created_at: at(20), you: false },
    ];
    this.sessions = [
      { id: uuid("90000000", 1), device: "Chrome · macOS", created_at: at(0.1), last_seen_at: at(0), expires_at: at(-0.3), current: true },
      { id: uuid("90000000", 2), device: "Safari · iPhone", created_at: at(1), last_seen_at: at(0.9), expires_at: at(0.7), current: false },
    ];
    this.record("login", null);
  }

  private record(action: string, household: string | null, detail: Json = {}) {
    this.audit.unshift({
      id: uuid("91000000", this.audit.length + 1),
      created_at: new Date(Date.parse(NOW) + this.audit.length * 60_000).toISOString(),
      action,
      admin_email: ADMIN_EMAIL,
      household_id: household,
      short_id: household ? short(household) : null,
      detail,
    });
  }

  private row(house: Household) {
    return {
      id: house.id,
      short_id: short(house.id),
      kind: house.kind,
      status: house.status,
      whatsapp: house.whatsapp,
      google: house.google,
      joined_at: house.joined,
      agreed_at: house.kind === "pending" ? null : house.joined,
      last_active_at: house.lastActive,
      plan: house.plan,
      language: house.language,
    };
  }

  private detail(house: Household) {
    return {
      ...this.row(house),
      suspended_at: house.suspendedAt,
      deleted_at: house.deletedAt,
      last_message_at: house.lastActive,
      last_record_at: house.lastActive,
      google_email: house.google ? "s***@***.com" : null,
      plan_detail: {
        state: house.plan,
        trial_ends_at: house.plan === "trial" ? at(-20) : null,
        paid_through: house.paidThrough,
        renewal: house.renewal,
        next_charge_on: house.renewal === "autopay" && house.paidThrough ? house.paidThrough.slice(0, 10) : null,
        grace_until: null,
      },
      payments: this.payments.filter((payment) => payment.household_id === house.id),
      usage: { ai: 3, voice: 9, ai_limit: 20, voice_limit: 10 },
      records: house.kind === "pending" || house.status === "deleted" ? {} : { confirmed: 12, needs_review: 2 },
      dues: house.status === "deleted" ? {} : { upcoming: 1 },
      budgets: house.status === "deleted" ? 0 : 2,
      goal_set: house.kind === "self_serve" && house.status !== "deleted",
      imports: house.kind === "self_serve" ? [{ mode: "gmail", status: "completed", error_code: null, started_at: at(4), finished_at: at(4) }] : [],
      statements: [],
      gmail: null,
      whatsapp_state: house.whatsapp && house.status !== "deleted"
        ? { replies_on: house.id !== adminIds.paused, agreed_at: null, reminders: true, checkins: false, language: house.language, last_message_at: house.lastActive }
        : null,
      actions: allowed(house),
    };
  }

  private find(id: string) {
    return this.households.find((house) => house.id === id) ?? null;
  }

  private search(query: URLSearchParams) {
    const text = (query.get("q") ?? "").trim().toLowerCase();
    const digits = text.replace(/[\s+()-]/g, "");
    let found = this.households;
    if (text) {
      if (/^\d{10,}$/.test(digits)) {
        const number = digits.length === 10 ? `91${digits}` : digits;
        found = found.filter((house) => house.phone === number);
      } else if (/^[0-9a-f-]{4,36}$/.test(text)) {
        found = found.filter((house) => house.id.replace(/-/g, "").startsWith(text.replace(/-/g, "").slice(0, 8)));
      } else {
        found = [];
      }
    }
    const kind = query.get("kind");
    const status = query.get("status");
    const plan = query.get("plan");
    const active = Number(query.get("active") ?? 0);
    if (kind) found = found.filter((house) => house.kind === kind);
    if (status) found = found.filter((house) => house.status === status);
    if (plan) found = found.filter((house) => house.plan === plan);
    if (active) found = found.filter((house) => house.lastActive && Date.parse(NOW) - Date.parse(house.lastActive) <= active * DAY);
    const offset = Number(query.get("offset") ?? 0);
    const items = found.slice(offset, offset + 50).map((house) => this.row(house));
    return { items, total: found.length, offset, next_offset: offset + 50 < found.length ? offset + 50 : null };
  }

  private act(house: Household, action: string, body: Json): FakeResponse {
    const name = ({ "sign-out": "sign_out", suspend: "suspend", restore: "restore", erase: "erase", premium: "premium", "autopay/cancel": "autopay_cancel", "pay-link": "pay_link" } as Record<string, Action>)[action];
    if (!name || !allowed(house).includes(name)) return envelope(409, "action_not_allowed");
    if (name === "erase") {
      if (body.confirm !== short(house.id)) return envelope(422, "confirmation_mismatch");
      this.record("household_erased", house.id, { via: house.kind });
      if (house.kind === "pending") this.households = this.households.filter((item) => item.id !== house.id);
      else if (house.kind === "pilot") Object.assign(house, { kind: "former_pilot", whatsapp: false });
      else Object.assign(house, { status: "deleted", deletedAt: NOW, whatsapp: false, google: false });
      return ok({ done: true });
    }
    if (name === "pay_link") {
      this.record("pay_link_created", house.id);
      return ok({ url: "http://127.0.0.1:3032/pay#synthetic-pay-link" });
    }
    if (name === "premium") {
      const days = Number(body.days);
      if (!Number.isInteger(days) || days < 1 || days > 366) return envelope(422, "validation_error");
      Object.assign(house, { plan: "active", paidThrough: new Date(Date.parse(NOW) + days * DAY).toISOString() });
      this.record("premium_granted", house.id, { days });
    } else if (name === "suspend") {
      Object.assign(house, { status: "suspended", suspendedAt: NOW, renewal: house.renewal === "autopay" ? "off" : house.renewal });
      this.record("household_suspended", house.id);
    } else if (name === "restore") {
      Object.assign(house, { status: "active", suspendedAt: null });
      this.record("household_restored", house.id);
    } else if (name === "autopay_cancel") {
      house.renewal = "off";
      this.record("autopay_cancelled", house.id);
    } else {
      this.record("household_signed_out", house.id);
    }
    return ok(this.detail(house));
  }

  handle(request: FakeRequest, appOrigin: string): FakeResponse {
    const { method, path, query } = request;
    const body = (request.body ?? {}) as Json;
    if (method === "POST" && request.origin !== appOrigin) return envelope(403, "origin_not_allowed");
    if (path === "/api/v1/admin/login" && method === "POST") {
      const password = this.mustChange ? TEMPORARY_PASSWORD : ADMIN_PASSWORD;
      if (String(body.email ?? "").trim().toLowerCase() !== ADMIN_EMAIL || body.password !== password) {
        return envelope(401, "admin_login_failed");
      }
      this.signedIn = true;
      this.record("login", null);
      return ok({ email: ADMIN_EMAIL, must_change_password: this.mustChange });
    }
    if (!this.signedIn) return envelope(401, "admin_required");
    if (this.mustChange && !PASSWORD_ROUTES.has(path)) return envelope(403, "admin_password_change_required");
    let match: RegExpMatchArray | null;

    if (path === "/api/v1/admin/session") return ok({ email: ADMIN_EMAIL, must_change_password: this.mustChange });
    if (path === "/api/v1/admin/logout" && method === "POST") {
      this.signedIn = false;
      this.record("logout", null);
      return ok({ done: true });
    }
    if (path === "/api/v1/admin/password" && method === "POST") {
      const current = this.mustChange ? TEMPORARY_PASSWORD : ADMIN_PASSWORD;
      if (body.current !== current) return envelope(401, "admin_login_failed");
      const next = String(body.new ?? "");
      if (next.length < 12 || next.toLowerCase() === ADMIN_EMAIL) return envelope(422, "weak_password");
      this.mustChange = false;
      this.record("password_changed", null);
      return ok({ email: ADMIN_EMAIL, must_change_password: false });
    }
    if (path === "/api/v1/admin/overview") {
      const counts = (key: keyof Household) =>
        this.households.reduce<Record<string, number>>((all, house) => {
          if (house.status !== "active") return all;
          const value = String(house[key]);
          all[value] = (all[value] ?? 0) + 1;
          return all;
        }, {});
      const households = counts("kind");
      for (const house of this.households) if (house.status !== "active") households[house.status] = (households[house.status] ?? 0) + 1;
      return ok({
        billing_enabled: true,
        households,
        signups: this.signups(),
        active: { today: 1, week: 3, month: 4 },
        plans: counts("plan"),
        paid_this_month: 1,
        received_this_month_minor: 29900,
        open_payments: 1,
        usage_today: { ai: 14, voice: 6 },
        deliveries_week: { delivered: 31, read: 18, failed: 1 },
        imports_week: { completed: 2 },
      });
    }
    if (path === "/api/v1/admin/system") {
      return ok({
        environment: "production",
        release: "1eadf04c0ffee",
        database: "connected",
        schema_status: "current",
        schema_head: "0014_admin",
        flags: { signup_enabled: true, whatsapp_enabled: true, billing_enabled: true, payu_autopay_enabled: false, billing_owner_included: true, triage_enabled: false, statement_import_enabled: false, gmail_for_new_accounts: false },
        limits: { signup_limit: 100, session_days: 30, daily_ai_limit: 20, daily_voice_limit: 10, admin_session_hours: 8 },
        providers: { assistant: "configured", transcription: "configured", english_hindi_speech: "configured", malayalam_speech: "missing", gmail: "configured", whatsapp: "configured", fast_decisions: "off", payu: "configured", email: "configured" },
        payu_environment: "production",
        active_imports: 0,
        open_payments: 1,
      });
    }
    if (path === "/api/v1/admin/households") return ok(this.search(query));
    if ((match = path.match(/^\/api\/v1\/admin\/households\/([0-9a-f-]{36})$/))) {
      const house = this.find(match[1] ?? "");
      return house ? ok(this.detail(house)) : envelope(404, "not_found");
    }
    if ((match = path.match(/^\/api\/v1\/admin\/households\/([0-9a-f-]{36})\/(.+)$/)) && method === "POST") {
      const house = this.find(match[1] ?? "");
      return house ? this.act(house, match[2] ?? "", body) : envelope(404, "not_found");
    }
    if (path === "/api/v1/admin/payments") {
      const status = query.get("status");
      const items = this.payments.filter((payment) => !status || payment.status === status);
      return ok({ items, total: items.length, offset: 0, next_offset: null });
    }
    if ((match = path.match(/^\/api\/v1\/admin\/payments\/([0-9a-f-]{36})\/reconcile$/)) && method === "POST") {
      const payment = this.payments.find((item) => item.id === match?.[1]);
      if (!payment) return envelope(404, "not_found");
      Object.assign(payment, { status: "paid", payu_id: "403993715500000001", covers_to: at(-30) });
      this.record("payment_reconciled", String(payment.household_id), { payment: String(payment.id) });
      return ok(payment);
    }
    if (path === "/api/v1/admin/signups") return ok(this.signups());
    if (path === "/api/v1/admin/signups/tidy" && method === "POST") {
      this.record("signups_tidied", null, { removed: this.stalePending });
      this.stalePending = 0;
      return ok(this.signups());
    }
    if (path === "/api/v1/admin/admins" && method === "GET") return ok(this.admins);
    if (path === "/api/v1/admin/admins" && method === "POST") {
      const email = String(body.email ?? "").trim().toLowerCase();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email)) return envelope(422, "invalid_contact");
      if (this.admins.some((admin) => admin.email === email)) return envelope(409, "admin_exists");
      const id = uuid("70000000", this.admins.length + 1);
      this.admins.push({ id, email, active: true, must_change_password: true, last_login_at: null, created_at: NOW, you: false });
      this.record("admin_created", null, { admin: id });
      return ok({ email, temporary_password: TEMPORARY_PASSWORD });
    }
    if ((match = path.match(/^\/api\/v1\/admin\/admins\/([0-9a-f-]{36})\/disable$/)) && method === "POST") {
      const admin = this.admins.find((item) => item.id === match?.[1]);
      if (!admin) return envelope(404, "not_found");
      if (admin.you) return envelope(409, "action_not_allowed");
      admin.active = false;
      this.record("admin_disabled", null, { admin: String(admin.id) });
      return ok(this.admins);
    }
    if (path === "/api/v1/admin/sessions") return ok(this.sessions);
    if (path === "/api/v1/admin/sessions/sign-out-others" && method === "POST") {
      const removed = this.sessions.length - 1;
      this.sessions = this.sessions.filter((row) => row.current);
      this.record("sessions_revoked", null, { removed });
      return ok(this.sessions);
    }
    if (path === "/api/v1/admin/audit") {
      const offset = Number(query.get("offset") ?? 0);
      return ok({ items: this.audit.slice(offset, offset + 50), total: this.audit.length, offset, next_offset: offset + 50 < this.audit.length ? offset + 50 : null });
    }
    return envelope(404, "not_found");
  }

  private signups() {
    return {
      enabled: true,
      open: true,
      agreed: 84,
      pending: 3,
      limit: 100,
      waitlist: 0,
      waitlist_languages: {},
      oldest_waiting_since: null,
      stale_pending: this.stalePending,
    };
  }
}
