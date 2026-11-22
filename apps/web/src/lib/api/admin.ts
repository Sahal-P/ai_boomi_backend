import { z } from "zod";
import { ApiError, apiFetch, failure, jsonBody, query, requestJson } from "./http.ts";

// The admin panel (docs/admin-round/contract.md). Every rule is enforced by the API; these
// schemas mirror its response models: who each household is (name, phone number and email, since
// docs/names-search-round/contract.md) and its activity, never its records, memories or hashes.
// The one exception is the messages page (docs/conversation-round/contract.md): what a household
// that agreed and FinBoy said, with its voice notes and photos. FinBoy's own ₹299 payments are the
// only money.

const ADMIN = "/api/v1/admin";
// The owner's household ID is not a random UUID, so IDs are checked as GUIDs.
const id = z.guid();
const instant = z.iso.datetime({ offset: true });
const shortId = z.string().regex(/^[0-9a-f]{8}$/);
const count = z.number().int().nonnegative();
const counts = z.record(z.string().max(40), count);
const language = z.enum(["en", "hi", "ml"]);
const name = z.string().max(200).nullable();
// Digits with the country code, like "919876543210".
const phone = z.string().regex(/^[0-9]{7,20}$/).nullable();

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
  name,
  phone,
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
  household_name: name,
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
  // The full email from the household's next Google sign-in on; until then "s***@***.com".
  google_email: z.string().max(254).nullable(),
  // What the household typed for PayU receipts.
  payer_email: z.string().max(254).nullable(),
  payer_phone: phone,
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
  // Absent from an API older than the conversation round.
  messages: z.object({ kept_from: instant.nullable(), declined_at: instant.nullable(), count }).optional(),
  actions: z.array(z.enum(ACTIONS)),
});
export type HouseholdDetail = z.infer<typeof householdDetailSchema>;

export const MESSAGE_KINDS = [
  "text",
  "voice",
  "photo",
  "document",
  "tap",
  "command",
  "buttons",
  "list",
  "voice_reply",
  "template",
] as const;
export type MessageKind = (typeof MESSAGE_KINDS)[number];
const messageRowSchema = z.object({
  id,
  at: instant,
  channel: z.enum(["whatsapp", "web"]),
  direction: z.enum(["in", "out"]),
  kind: z.enum(MESSAGE_KINDS),
  text: z.string().max(4096).nullable(),
  transcript: z.string().max(4096).nullable(),
  language: language.nullable(),
  // Titles FinBoy offered, or the choice a tap made.
  choices: z.array(z.string().max(64)).max(10),
  media: z.enum(["audio", "image"]).nullable(),
  media_bytes: count.nullable(),
  status: z.enum(["sending", "sent", "delivered", "read", "failed", "unknown"]).nullable(),
  outcome: z.string().max(64).nullable(),
});
export type MessageRow = z.infer<typeof messageRowSchema>;
const messagePageSchema = z.object({
  kept_from: instant.nullable(),
  declined_at: instant.nullable(),
  items: z.array(messageRowSchema).max(50), // newest first
  // The oldest message shown ("<time>|<id>"), passed back as `before` for the page before it.
  next_before: z.string().max(100).nullable(),
});
export type MessagePage = z.infer<typeof messagePageSchema>;
// Household feedback (docs/feedback-round/contract.md): lists carry no words; opening one does.
export const FEEDBACK_STATUSES = ["new", "planned", "done"] as const;
export type FeedbackStatus = (typeof FEEDBACK_STATUSES)[number];
const feedbackRowSchema = z.object({
  id,
  household_id: id,
  short_id: shortId,
  household_name: name,
  kind: z.enum(["problem", "idea", "other"]),
  status: z.enum(FEEDBACK_STATUSES),
  has_screenshot: z.boolean(),
  created_at: instant,
});
export type FeedbackRow = z.infer<typeof feedbackRowSchema>;
const feedbackPageSchema = page(feedbackRowSchema).extend({ new: count });
export type FeedbackPage = z.infer<typeof feedbackPageSchema>;
const feedbackDetailSchema = feedbackRowSchema.extend({
  message: z.string().min(1).max(2000),
  page: z.string().max(200),
  status_changed_at: instant.nullable(),
});
export type FeedbackDetail = z.infer<typeof feedbackDetailSchema>;
// A screenshot is redrawn in the browser to at most 1.5 MB before it is sent.
export const SCREENSHOT_LIMIT = 1_500_000;

// The largest voice note or photo FinBoy keeps (WhatsApp photos are at most 5 MB).
export const MEDIA_LIMIT = 5 * 1024 * 1024;

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
  feedback_new: count,
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
  // window_only: the advisor's coach before Meta approves its template (advisor phase 3).
  providers: z.record(z.string().max(64), z.enum(["configured", "missing", "disabled", "off", "window_only"])),
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
    household_name: name,
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

export const getMessages = async (householdId: string, before: string | null, signal?: AbortSignal) =>
  requestJson(
    `${ADMIN}/households/${segment(householdId)}/messages${query({ before })}`,
    messagePageSchema,
    { signal },
  );

/** A kept voice note or photo, through the API so each open is signed in and recorded. */
export async function getMessageMedia(messageId: string, signal?: AbortSignal): Promise<Blob> {
  const response = await apiFetch(`${ADMIN}/messages/${segment(messageId)}/media`, {
    headers: { Accept: "audio/*, image/*" },
    signal,
    timeoutMs: 30_000,
  });
  if (!response.ok) throw await failure(response);
  const type = response.headers.get("content-type")?.split(";")[0]?.trim() ?? "";
  const data = /^(audio|image)\/[a-z0-9.+-]+$/.test(type) ? await response.blob() : null;
  if (!data || !data.size || data.size > MEDIA_LIMIT) {
    throw new ApiError("FinBoy received an unexpected file.", response.status, { kind: "invalid_response" });
  }
  return data;
}

export const listAdminFeedback = (status: FeedbackStatus | null, offset: number, signal?: AbortSignal) =>
  requestJson(`${ADMIN}/feedback${query({ status, offset: offset || null })}`, feedbackPageSchema, { signal });
/** One report with its words; each open is recorded in the audit log. */
export const getAdminFeedback = async (feedbackId: string, signal?: AbortSignal) =>
  requestJson(`${ADMIN}/feedback/${segment(feedbackId)}`, feedbackDetailSchema, { signal });
export const setFeedbackStatus = async (feedbackId: string, status: FeedbackStatus) =>
  requestJson(`${ADMIN}/feedback/${segment(feedbackId)}`, feedbackDetailSchema, {
    method: "PATCH",
    ...jsonBody({ status }),
  });

/** A report's screenshot, through the API so each open is signed in and recorded. */
export async function getFeedbackScreenshot(feedbackId: string, signal?: AbortSignal): Promise<Blob> {
  const response = await apiFetch(`${ADMIN}/feedback/${segment(feedbackId)}/screenshot`, {
    headers: { Accept: "image/*" },
    signal,
    timeoutMs: 30_000,
  });
  if (!response.ok) throw await failure(response);
  const type = response.headers.get("content-type")?.split(";")[0]?.trim() ?? "";
  const data = ["image/png", "image/jpeg", "image/webp"].includes(type) ? await response.blob() : null;
  if (!data || !data.size || data.size > SCREENSHOT_LIMIT) {
    throw new ApiError("FinBoy received an unexpected file.", response.status, { kind: "invalid_response" });
  }
  return data;
}

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
  "/admin/households/messages",
  "/admin/payments",
  "/admin/signups",
  "/admin/feedback",
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
