import { ApiError } from "@/lib/api/http";

export type Problem = {
  /** What could not be done, in task terms. */
  title: string;
  /** Whether anything changed and what the person can do next. */
  detail: string;
  /** Generated request ID for support; never request content. */
  reference: string | null;
  kind: ApiError["kind"] | "unknown";
  code: string | null;
};

// Fixed backend codes with their own recovery copy (contract v1 plus phase-1 mail codes).
const byCode: Record<string, string> = {
  version_conflict:
    "Your records changed since this was loaded. Nothing was saved. Review the latest version, then try again.",
  decision_conflict:
    "Someone or something changed this record after your decision. Nothing was overwritten. Review the latest version.",
  import_busy: "Another import is still running. Wait for it to finish, then try again.",
  demo_read_only: "The sample is read-only. It never changes your household records.",
  original_files_required:
    "Uploaded emails aren't kept, so FinBoy needs the original .eml files again to retry them.",
  source_unavailable: "Gmail is unavailable right now. Nothing changed. Try again shortly.",
  reconnect_required: "Google access expired or was revoked. Reconnect Gmail to scan again.",
  upload_limit: "That batch is too large. Choose up to 50 .eml files of 2 MB or less each.",
  invalid_eml: "One or more files aren't readable emails. Nothing was imported.",
  invalid_credentials: "That password didn't work. Check it and try again.",
  try_later: "Too many sign-in attempts. Wait a minute, then try again.",
  origin_not_allowed: "This page isn't allowed to make that change. Reload FinBoy and try again.",
  origin_denied: "This page isn't allowed to make that change. Reload FinBoy and try again.",
};

const byKind: Record<Problem["kind"], string> = {
  session: "Your private session ended. Sign in again to continue — this page keeps your unsaved work.",
  forbidden: "This page isn't allowed to make that change. Reload FinBoy and try again.",
  not_found: "It may have been removed or never existed. Nothing changed.",
  conflict: "Something changed since this was loaded. Nothing was saved. Refresh and try again.",
  validation: "Some values weren't accepted. Nothing was saved. Check them and try again.",
  rate_limited: "Too many requests. Wait a minute, then try again.",
  unavailable: "FinBoy is temporarily unavailable. Nothing changed. Try again in a minute.",
  offline: "You're offline. Nothing changed. Reconnect, then try again.",
  network: "FinBoy couldn't be reached. Nothing changed. Check your connection and try again.",
  timeout: "FinBoy took too long to respond. It may still finish; refresh before trying again.",
  invalid_response:
    "FinBoy sent something unexpected, so it wasn't shown. Try again; if it repeats, share the reference.",
  configuration: "This app isn't configured correctly. Contact the person who set it up.",
  unknown: "Something went wrong. Nothing changed. Try again.",
};

/** One content map for failures: the task affected, whether data changed, the next action. */
export function describeProblem(error: unknown, title: string): Problem {
  if (error instanceof ApiError) {
    return {
      title,
      detail: (error.code && byCode[error.code]) || byKind[error.kind],
      reference: error.requestId ?? null,
      kind: error.kind,
      code: error.code ?? null,
    };
  }
  return { title, detail: byKind.unknown, reference: null, kind: "unknown", code: null };
}

export function isConflict(error: unknown): boolean {
  return error instanceof ApiError && error.kind === "conflict";
}

export function hasCode(error: unknown, code: string): boolean {
  return error instanceof ApiError && error.code === code;
}
