import { z } from "zod";
import { apiBaseUrl, requestJson } from "./http.ts";

const connectionSchema = z.object({
  id: z.uuid(),
  provider: z.literal("gmail"),
  account_email_masked: z.string().max(320),
  status: z.enum(["active", "paused", "error", "revoked"]),
  last_synced_at: z.iso.datetime({ offset: true }).nullable(),
});
const startedSchema = z.object({ import_run_id: z.uuid() });
const okSchema = z.object({ status: z.literal("ok") });
export type MailConnection = z.infer<typeof connectionSchema>;

export function authorizeUrl(): string {
  return `${apiBaseUrl()}/api/v1/connections/gmail/authorize`;
}

export const getConnections = (signal?: AbortSignal) =>
  requestJson("/api/v1/connections", z.array(connectionSchema), { signal });
/** Starts a new manual scan job; it never resumes an earlier run. */
export const scanNow = (id: string) =>
  requestJson(`/api/v1/connections/${encodeURIComponent(id)}/sync`, startedSchema, {
    method: "POST",
  });
/** Pausing stops future scans and asks an active scan to stop at a safe checkpoint. */
export const setScansAllowed = (id: string, allowed: boolean) =>
  requestJson(
    `/api/v1/connections/${encodeURIComponent(id)}/${allowed ? "resume" : "pause"}`,
    okSchema,
    { method: "POST" },
  );
/** Revokes Google access; imported records are handled separately through the deletion preview. */
export const disconnectConnection = (id: string) =>
  requestJson(`/api/v1/connections/${encodeURIComponent(id)}?delete_data=false`, okSchema, {
    method: "DELETE",
    timeoutMs: 60_000,
  });

const oauthErrors = {
  gmail_not_configured: "Gmail connection isn't set up on this server yet. You can upload emails instead.",
  invalid_state: "This connection link expired or was already used. Connect Gmail again.",
  consent_denied: "Gmail access was cancelled. Nothing was imported. Connect again whenever you're ready.",
  scope_missing: "FinBoy needs read-only Gmail access. Reconnect and allow that permission.",
  refresh_token_missing: "Google didn't grant ongoing access. Reconnect Gmail to scan again.",
  reconnect_required: "Google access expired or was revoked. Reconnect Gmail to scan again.",
  authorization_failed: "Google access couldn't be used. Reconnect Gmail to scan again.",
  configuration_missing: "Gmail isn't set up on this server yet. You can upload emails instead.",
  provider_unavailable: "Gmail is unavailable right now. Nothing was imported. Try again shortly.",
  import_busy: "Another import is still running. Wait for it to finish, then try again.",
} as const;
export type OAuthErrorCode = keyof typeof oauthErrors;

export function isOAuthErrorCode(code: string): code is OAuthErrorCode {
  return Object.hasOwn(oauthErrors, code);
}

export function oauthErrorMessage(code?: string | null): string | null {
  if (!code) return null;
  return isOAuthErrorCode(code)
    ? oauthErrors[code]
    : "Gmail couldn't be connected. Nothing was imported. Try again.";
}
