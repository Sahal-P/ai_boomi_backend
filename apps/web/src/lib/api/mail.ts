import { z } from "zod";
import { ApiError, requestJson } from "@/lib/api/http";

const counter = z.number().int().nonnegative();
export const importRunSchema = z.object({
  id: z.uuid(),
  mode: z.enum(["gmail", "eml_upload", "demo_mailbox"]),
  status: z.enum(["queued", "running", "completed", "failed"]),
  headers_checked: counter,
  candidates_found: counter,
  emails_processed: counter,
  events_extracted: counter,
  transactions_created: counter,
  duplicates_merged: counter,
  needs_review: counter,
  non_financial_skipped: counter,
  failed: counter,
  error_code: z.string().nullable(),
});
const connectionSchema = z.object({
  id: z.uuid(), provider: z.literal("gmail"), account_email_masked: z.string(),
  status: z.enum(["active", "paused", "error", "revoked"]),
  last_synced_at: z.iso.datetime({ offset: true }).nullable(),
});
const auditSchema = z.object({
  id: z.uuid(), event_type: z.string(), subject_type: z.string(),
  subject_id: z.uuid(), created_at: z.iso.datetime({ offset: true }),
});
const startedSchema = z.object({ import_run_id: z.uuid() });
const okSchema = z.object({ status: z.literal("ok") });
export type ImportRun = z.infer<typeof importRunSchema>;
export type MailConnection = z.infer<typeof connectionSchema>;
export type AuditEvent = z.infer<typeof auditSchema>;

export function authorizeUrl(): string {
  const base = new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000");
  if (!["http:", "https:"].includes(base.protocol) || base.username || base.password) {
    throw new Error("The backend URL is not configured correctly.");
  }
  return new URL("/api/v1/connections/gmail/authorize", base).toString();
}

export const getImportRun = (id: string, signal?: AbortSignal) =>
  requestJson(`/api/v1/imports/${encodeURIComponent(id)}`, importRunSchema, { signal });
export const getConnections = (signal?: AbortSignal) =>
  requestJson("/api/v1/connections", z.array(connectionSchema), { signal });
export const getAuditEvents = (signal?: AbortSignal) =>
  requestJson("/api/v1/privacy/audit-events", z.array(auditSchema), { signal });
export const startDemo = () =>
  requestJson("/api/v1/imports/demo", startedSchema, { method: "POST" });
export function uploadEml(files: File[]) {
  if (!files.length || files.length > 50 || files.some((file) =>
    !file.name.toLowerCase().endsWith(".eml") || file.size > 2 * 1024 * 1024)) {
    throw new Error("Choose 1–50 .eml files, up to 2 MB each.");
  }
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return requestJson("/api/v1/imports/eml", startedSchema, { method: "POST", body, timeoutMs: 30_000 });
}
export const syncConnection = (id: string) => requestJson(
  `/api/v1/connections/${encodeURIComponent(id)}/sync`, startedSchema, { method: "POST" });
export const setConnectionPaused = (id: string, paused: boolean) => requestJson(
  `/api/v1/connections/${encodeURIComponent(id)}/${paused ? "pause" : "resume"}`,
  okSchema, { method: "POST" });
export const disconnectConnection = (id: string, deleteData: boolean) => requestJson(
  `/api/v1/connections/${encodeURIComponent(id)}?delete_data=${deleteData}`,
  okSchema, { method: "DELETE", timeoutMs: 60_000 });
export const deleteImportedData = () => requestJson(
  "/api/v1/privacy/imported-data", okSchema, { method: "DELETE", timeoutMs: 30_000 });

const errors = {
  gmail_not_configured: "Gmail connection is not configured yet. You can upload emails or try the demo.",
  invalid_state: "This connection link expired or was already used. Please connect Gmail again.",
  consent_denied: "Gmail access was cancelled. You can connect again whenever you’re ready.",
  scope_missing: "Read-only Gmail access is required. Please reconnect and allow that permission.",
  refresh_token_missing: "Google did not return offline access. Please reconnect Gmail.",
  reconnect_required: "Google access expired or was revoked. Please reconnect Gmail.",
  import_cancelled: "This import stopped because the connection changed or the data was deleted.",
  import_busy: "Another import is in progress. Let it finish, then try again.",
  demo_unavailable: "The demo mailbox is not available yet. Please try again shortly.",
  authorization_failed: "Google access could not be used. Please reconnect Gmail.",
  configuration_missing: "Gmail is not configured yet. Please try upload or demo mode.",
  provider_unavailable: "The email provider is unavailable. Please try again shortly.",
};
function isErrorCode(code: string): code is keyof typeof errors {
  return Object.hasOwn(errors, code);
}
export function oauthErrorMessage(code?: string): string | null {
  return code ? (isErrorCode(code) ? errors[code] : "The operation could not be completed. Please try again.") : null;
}
export function mailErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return errors.import_busy;
    if (error.status === 413) return "Choose up to 50 .eml files, no larger than 2 MB each.";
    if (error.status === 400 || error.status === 422) return "Please check your files or reconnect Gmail and try again.";
    if (error.status === 404) return "This import or connection could not be found.";
    return "FinBoy could not reach the mail service. Check the API connection and try again.";
  }
  return "Could not complete this action. Check your connection and try again.";
}
