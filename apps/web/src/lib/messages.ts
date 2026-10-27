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

// Fixed backend codes with their own recovery copy (contract v1.1.2 plus phase-1 mail codes).
const byCode: Record<string, string> = {
  version_conflict:
    "Your records changed since this was loaded. Nothing was saved. Review the latest version, then try again.",
  decision_conflict:
    "Someone or something changed this record after your decision. Nothing was overwritten. Review the latest version.",
  import_busy: "Another import is still running. Wait for it to finish, then try again.",
  demo_read_only: "The sample is read-only. It never changes your household records.",
  original_files_required:
    "Uploaded emails aren't kept, so FinBoy needs the original .eml files again to retry them.",
  invalid_decision:
    "Those changes don't fit together — for example a refund marked as money going out. Nothing was saved. Check the fields and try again.",
  quarantined_record:
    "This record mixes sample and household evidence, so it's on hold and can't be decided here. Nothing changed.",
  database_unavailable: "Your records are temporarily unavailable. Nothing changed. Try again shortly.",
  source_lineage_unavailable:
    "Some older merged records can't be traced to their emails, so nothing was deleted. Ask the person who set up FinBoy to check them first.",
  source_unavailable: "Gmail is unavailable right now. Nothing changed. Try again shortly.",
  reconnect_required: "Google access expired or was revoked. Reconnect Gmail to scan again.",
  upload_limit: "That batch is too large. Choose up to 50 .eml files of 2 MB or less each.",
  invalid_eml: "One or more files aren't readable emails. Nothing was imported.",
  invalid_credentials: "That password didn't work. Check it and try again.",
  try_later: "Too many sign-in attempts. Wait a minute, then try again.",
  origin_not_allowed: "This page isn't allowed to make that change. Reload FinBoy and try again.",
  origin_denied: "This page isn't allowed to make that change. Reload FinBoy and try again.",
  // Sign-up round (docs/signup-round/contract.md).
  invalid_sign_in: "That sign-in didn't work. Nothing changed. Please try again.",
  sign_in_unavailable: "This way of signing in isn't available right now. Try the other option.",
  signup_unavailable: "New accounts aren't open yet. You can look around the sample in the meantime.",
  signups_closed:
    "FinBoy is full for now. Send JOIN to FinBoy on WhatsApp and we'll message you when there's a place.",
  login_expired: "That sign-in request expired. Start again — it only takes a moment.",
  login_declined: "You tapped No on WhatsApp, so nobody was signed in.",
  already_linked: "That account already belongs to another FinBoy household, so it wasn't linked.",
  usage_limit: "You've used FinBoy a lot today. Nothing changed. Please try again tomorrow.",
  owner_household: "The owner's household can't be deleted here.",
  web_not_available: "Your household uses FinBoy on WhatsApp.",
  entry_busy: "FinBoy is still saving your last entry. Nothing was added twice. Try again in a moment.",
  entry_unavailable: "That entry couldn't be saved. Nothing was added. Try again.",
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
