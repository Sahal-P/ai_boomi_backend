import { z } from "zod";
import { ApiError, jsonBody, query, requestJson } from "./http.ts";

// The admin panel (docs/admin-round/contract.md). Every rule is enforced by the API; these
// schemas mirror its response models, which carry activity only: no household's records,
// contact details, names or hashes. FinBoy's own ₹299 payments are the only money.

const ADMIN = "/api/v1/admin";
// The owner's household ID is not a random UUID, so IDs are checked as GUIDs.
const id = z.guid();
const instant = z.iso.datetime({ offset: true });
const shortId = z.string().regex(/^[0-9a-f]{8}$/);
const count = z.number().int().nonnegative();
const counts = z.record(z.string().max(40), count);
const language = z.enum(["en", "hi", "ml"]);

export const KINDS = ["owner", "pilot", "self_serve", "pending", "former_pilot"] as const;
export const STATUSES = ["active", "suspended", "deleted"] as const;
export const PLAN_STATES = ["included", "trial", "active", "grace", "free"] as const;
export const PAYMENT_STATUSES = ["started", "scheduled", "pending", "paid", "failed", "abandoned"] as const;
export const ACTIONS = ["sign_out", "suspend", "restore", "erase", "premium", "autopay_cancel", "pay_link"] as const;
export type Kind = (typeof KINDS)[number];
export type HouseholdStatus = (typeof STATUSES)[number];
export type PlanState = (typeof PLAN_STATES)[number];
export type PaymentStatus = (typeof PAYMENT_STATUSES)[number];
export type HouseholdAction = (typeof ACTIONS)[number];

const adminSessionSchema = z.object({ email: z.string().max(254), must_change_password: z.boolean() });
export type AdminSession = z.infer<typeof adminSessionSchema>;
const doneSchema = z.object({ done: z.literal(true) });

const householdRowSchema = z.object({
  id,
  short_id: shortId,
  kind: z.enum(KINDS),
  status: z.enum(STATUSES),
  whatsapp: z.boolean(),
  google: z.boolean(),
  joined_at: instant,
  agreed_at: instant.nullable(),
  last_active_at: instant.nullable(),
  plan: z.enum(PLAN_STATES),
  language: language.nullable(),
});
export type HouseholdRow = z.infer<typeof householdRowSchema>;

const page = <T extends z.ZodType>(item: T) =>
  z.object({ items: z.array(item), total: count, offset: count, next_offset: count.nullable() });

const householdPageSchema = page(householdRowSchema);
export type HouseholdPage = z.infer<typeof householdPageSchema>;

const paymentSchema = z.object({
  id,
  household_id: id,
  short_id: shortId,
  created_at: instant,
  amount_minor: z.number().int().positive(),
  status: z.enum(PAYMENT_STATUSES),
  kind: z.enum(["checkout", "renewal"]),
  mode: z.string().max(12).nullable(),
  txnid: z.string().max(64),
  payu_id: z.string().max(64).nullable(),
  error_code: z.string().max(64).nullable(),
  covers_to: instant.nullable(),
});
export type AdminPayment = z.infer<typeof paymentSchema>;
const paymentPageSchema = page(paymentSchema);
export type PaymentPage = z.infer<typeof paymentPageSchema>;

const householdDetailSchema = householdRowSchema.extend({
  suspended_at: instant.nullable(),
  deleted_at: instant.nullable(),
  last_message_at: instant.nullable(),
  last_record_at: instant.nullable(),
  // Stored masked by the sign-up round ("s***@***.com"); nothing is decrypted.
  google_email: z.string().max(120).nullable(),
  plan_detail: z.object({
    state: z.enum(PLAN_STATES),
    trial_ends_at: instant.nullable(),
    paid_through: instant.nullable(),
    renewal: z.enum(["manual", "autopay", "off"]).nullable(),
    next_charge_on: z.iso.date().nullable(),
    grace_until: instant.nullable(),
  }),
  payments: z.array(paymentSchema),
  usage: z.object({ ai: count, voice: count, ai_limit: count, voice_limit: count }),
  records: counts,
  dues: counts,
  budgets: count,
  goal_set: z.boolean(),
  imports: z.array(
    z.object({
      mode: z.string().max(32),
      status: z.string().max(32),
      error_code: z.string().max(64).nullable(),
      started_at: instant.nullable(),
      finished_at: instant.nullable(),
    }),
  ),
  statements: z.array(
    z.object({
      period_start: z.iso.date(),
      period_end: z.iso.date(),
      pages: count,
      rows_total: count,
      reconciled: z.boolean(),
      removed: z.boolean(),
    }),
  ),
  gmail: z
    .object({ status: z.string().max(32), connected_at: instant, last_synced_at: instant.nullable(), revoked: z.boolean() })
    .nullable(),
  whatsapp_state: z
    .object({
      replies_on: z.boolean(),
      agreed_at: instant.nullable(),
      reminders: z.boolean(),
      checkins: z.boolean(),
      language: language.nullable(),
      last_message_at: instant.nullable(),
    })
    .nullable(),
  actions: z.array(z.enum(ACTIONS)),
});
export type HouseholdDetail = z.infer<typeof householdDetailSchema>;

const signupSchema = z.object({
  enabled: z.boolean(),
  open: z.boolean(),
  agreed: count,
  pending: count,
  limit: count,
  waitlist: count,
  waitlist_languages: counts,
  oldest_waiting_since: instant.nullable(),
  stale_pending: count,
});
export type SignupCounts = z.infer<typeof signupSchema>;

const overviewSchema = z.object({
  billing_enabled: z.boolean(),
  households: counts,
  signups: signupSchema,
  active: counts,
  plans: counts,
  paid_this_month: count,
  received_this_month_minor: count,
  open_payments: count,
  usage_today: counts,
  deliveries_week: counts,
  imports_week: counts,
});
export type Overview = z.infer<typeof overviewSchema>;

const systemSchema = z.object({
  environment: z.string().max(32),
  release: z.string().max(40).nullable(),
  database: z.enum(["connected", "unavailable"]),
  schema_status: z.enum(["current", "behind", "unavailable"]),
  schema_head: z.string().max(64),
  flags: z.record(z.string().max(64), z.boolean()),
  limits: z.record(z.string().max(64), z.number().int()),
  providers: z.record(z.string().max(64), z.enum(["configured", "missing", "disabled", "off"])),
  payu_environment: z.string().max(32),
  active_imports: count.nullable(),
  open_payments: count.nullable(),
});
export type SystemStatus = z.infer<typeof systemSchema>;

const adminRowSchema = z.object({
  id,
  email: z.string().max(254),
  active: z.boolean(),
  must_change_password: z.boolean(),
  last_login_at: instant.nullable(),
  created_at: instant,
  you: z.boolean(),
});
export type AdminRow = z.infer<typeof adminRowSchema>;

const sessionRowSchema = z.object({
  id,
  device: z.string().max(64),
  created_at: instant,
  last_seen_at: instant,
  expires_at: instant,
  current: z.boolean(),
});
export type SessionRow = z.infer<typeof sessionRowSchema>;

const auditPageSchema = page(
  z.object({
    id,
    created_at: instant,
    action: z.string().max(40),
    admin_email: z.string().max(254).nullable(),
    household_id: id.nullable(),
    short_id: shortId.nullable(),
    detail: z.record(z.string().max(16), z.union([z.string().max(64), z.number().int()])),
  }),
);
export type AuditPage = z.infer<typeof auditPageSchema>;
export type AuditRow = AuditPage["items"][number];

const createdAdminSchema = z.object({ email: z.string().max(254), temporary_password: z.string().min(12).max(256) });
export type CreatedAdmin = z.infer<typeof createdAdminSchema>;
const payLinkSchema = z.object({ url: z.url().max(2048) });

// Admin writes always carry a small JSON body: the API caps them by Content-Length.
const post = (body: Record<string, unknown> = {}) => ({ method: "POST", ...jsonBody(body) });

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** Only an ID ever goes into a path. */
function segment(value: string): string {
  if (!GUID.test(value)) throw new ApiError("That ID isn't valid.", undefined, { kind: "validation" });
  return value.toLowerCase();
}

export const getAdminSession = (signal?: AbortSignal) =>
  requestJson(`${ADMIN}/session`, adminSessionSchema, { signal });
export const adminSignIn = (email: string, password: string) =>
  requestJson(`${ADMIN}/login`, adminSessionSchema, post({ email, password }));
export const adminSignOut = () => requestJson(`${ADMIN}/logout`, doneSchema, post());
export const changeAdminPassword = (current: string, next: string) =>
  requestJson(`${ADMIN}/password`, adminSessionSchema, post({ current, new: next }));

export const getOverview = (signal?: AbortSignal) => requestJson(`${ADMIN}/overview`, overviewSchema, { signal });
export const getSystem = (signal?: AbortSignal) => requestJson(`${ADMIN}/system`, systemSchema, { signal });

export type HouseholdFilters = {
  q?: string | null;
  kind?: Kind | null;
  status?: HouseholdStatus | null;
  plan?: PlanState | null;
  active?: 7 | 30 | null;
  offset?: number | null;
};
export const listHouseholds = (filters: HouseholdFilters, signal?: AbortSignal) =>
  requestJson(
    `${ADMIN}/households${query({ ...filters, q: filters.q?.trim().slice(0, 64), offset: filters.offset || null })}`,
    householdPageSchema,
    { signal },
  );
// Async, so an invalid ID rejects like any other failure instead of throwing synchronously.
export const getHousehold = async (householdId: string, signal?: AbortSignal) =>
  requestJson(`${ADMIN}/households/${segment(householdId)}`, householdDetailSchema, { signal });

export type SimpleAction = "sign-out" | "suspend" | "restore" | "autopay/cancel";
export const actOnHousehold = async (householdId: string, action: SimpleAction) =>
  requestJson(`${ADMIN}/households/${segment(householdId)}/${action}`, householdDetailSchema, post());
export const grantPremium = async (householdId: string, days: number) =>
  requestJson(`${ADMIN}/households/${segment(householdId)}/premium`, householdDetailSchema, post({ days }));
export const createPayLink = async (householdId: string) =>
  requestJson(`${ADMIN}/households/${segment(householdId)}/pay-link`, payLinkSchema, post());
export const eraseHousehold = async (householdId: string, confirm: string) =>
  requestJson(`${ADMIN}/households/${segment(householdId)}/erase`, doneSchema, post({ confirm }));

export const listAdminPayments = (status: PaymentStatus | null, offset: number, signal?: AbortSignal) =>
  requestJson(`${ADMIN}/payments${query({ status, offset: offset || null })}`, paymentPageSchema, { signal });
export const reconcilePayment = async (paymentId: string) =>
  requestJson(`${ADMIN}/payments/${segment(paymentId)}/reconcile`, paymentSchema, post());

export const getSignups = (signal?: AbortSignal) => requestJson(`${ADMIN}/signups`, signupSchema, { signal });
export const tidySignups = () => requestJson(`${ADMIN}/signups/tidy`, signupSchema, post());

export const listAdmins = (signal?: AbortSignal) => requestJson(`${ADMIN}/admins`, z.array(adminRowSchema), { signal });
export const addAdmin = (email: string) => requestJson(`${ADMIN}/admins`, createdAdminSchema, post({ email }));
export const disableAdmin = async (adminId: string) =>
  requestJson(`${ADMIN}/admins/${segment(adminId)}/disable`, z.array(adminRowSchema), post());
export const listAdminSessions = (signal?: AbortSignal) =>
  requestJson(`${ADMIN}/sessions`, z.array(sessionRowSchema), { signal });
export const signOutOtherSessions = () =>
  requestJson(`${ADMIN}/sessions/sign-out-others`, z.array(sessionRowSchema), post());

export const getAudit = (offset: number, signal?: AbortSignal) =>
  requestJson(`${ADMIN}/audit${query({ offset: offset || null })}`, auditPageSchema, { signal });

const ADMIN_PATHS = [
  "/admin",
  "/admin/households",
  "/admin/payments",
  "/admin/signups",
  "/admin/system",
  "/admin/admins",
  "/admin/audit",
  "/admin/password",
];

/** Accepts only an admin page (with its query) as the place to return to after signing in. */
export function safeAdminReturnPath(value: string | null | undefined): string {
  const fallback = "/admin";
  if (!value || value.length > 512 || !value.startsWith("/") || /^\/[\\/]/.test(value)) return fallback;
  try {
    const base = "https://finboy.invalid";
    const url = new URL(value, base);
    if (url.origin !== base || url.username || url.password) return fallback;
    return ADMIN_PATHS.includes(url.pathname) ? `${url.pathname}${url.search}` : fallback;
  } catch {
    return fallback;
  }
}
