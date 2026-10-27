import type { ImportRun } from "./api/imports.ts";

export type OutcomeTone = "progress" | "success" | "attention" | "problem";
export type OutcomeAction =
  | { kind: "review"; label: string }
  | { kind: "overview"; label: string }
  | { kind: "sources"; label: string }
  | { kind: "retry_gmail"; label: string }
  | { kind: "continue_gmail"; label: string }
  | { kind: "select_files"; label: string };

export type ImportOutcomeCopy = {
  tone: OutcomeTone;
  title: string;
  detail: string[];
  primary: OutcomeAction | null;
  secondary: OutcomeAction[];
};

const plural = (count: number, one: string, many: string) =>
  `${count} ${count === 1 ? one : many}`;

const stopReasons: Record<string, string> = {
  reconnect_required: "Google access expired or was revoked, so the scan stopped.",
  import_cancelled: "The connection changed or data was deleted while it ran.",
  provider_unavailable: "Gmail was unavailable while it ran.",
  import_busy: "Another import was already running.",
};

function retryAction(run: ImportRun): OutcomeAction | null {
  if (!run.retryable) return null;
  if (run.retry_strategy === "refetch_gmail") {
    return {
      kind: "retry_gmail",
      label: run.failed ? `Retry ${plural(run.failed, "email", "emails")}` : "Retry failed emails",
    };
  }
  if (run.retry_strategy === "select_original_files") {
    return { kind: "select_files", label: "Select the original files again" };
  }
  return null;
}

/**
 * Turns run status and counters into the outcome people need: what changed, what didn't,
 * what failed and what to do next. Counts are shown as reported; no totals are derived here.
 */
export function importOutcome(run: ImportRun): ImportOutcomeCopy {
  const review = run.needs_review;
  const created = run.transactions_created;
  const merged = run.duplicates_merged;
  const failed = run.failed;
  const retry = retryAction(run);
  const reviewAction: OutcomeAction = {
    kind: "review",
    label: `Review ${plural(review, "record", "records")}`,
  };
  const notes: string[] = [];
  if (merged) {
    notes.push(
      `${plural(merged, "duplicate notification was", "duplicate notifications were")} linked to records you already had instead of creating new ones.`,
    );
  }
  const continuation: OutcomeAction | null = run.can_continue
    ? { kind: "continue_gmail", label: "Continue scanning this window" }
    : null;
  if (run.truncated) {
    notes.push(
      run.can_continue
        ? "This scan reached its limit, so some emails in the window weren't checked yet. Continue scanning to check the rest — emails already imported are skipped."
        : "This scan reached its limit, so some emails in the window weren't checked. Run another scan from Sources — emails already imported are skipped.",
    );
  }

  if (run.outcome === "queued" || run.outcome === "running") {
    return {
      tone: "progress",
      title: run.cancel_requested
        ? "Stopping at the next safe point…"
        : run.outcome === "queued"
          ? "Getting ready to import"
          : "Importing your emails…",
      detail: [
        run.candidates_found
          ? `${run.emails_processed} of ${plural(run.candidates_found, "possible money email", "possible money emails")} checked so far.`
          : "Looking for possible money emails.",
        "You can leave this page — the import keeps running, and you'll find it under Sources.",
      ],
      primary: null,
      secondary: [],
    };
  }

  if (run.outcome === "cancelled") {
    return {
      tone: "attention",
      title: "Import cancelled",
      detail: [
        "You stopped this import. Records saved before it stopped are kept; nothing else was imported.",
        ...notes,
      ],
      primary: review ? reviewAction : { kind: "sources", label: "Back to Sources" },
      secondary: review ? [{ kind: "sources", label: "Back to Sources" }] : [],
    };
  }

  if (run.outcome === "interrupted" || run.outcome === "failed") {
    const reason = (run.error_code && stopReasons[run.error_code]) || null;
    return {
      tone: "problem",
      title: run.outcome === "interrupted" ? "Import was interrupted" : "Import stopped",
      detail: [
        reason ??
          (run.outcome === "interrupted"
            ? "It stopped before finishing, for example because the server restarted."
            : "Something went wrong while importing."),
        created || review
          ? `Records saved before it stopped are kept${review ? `; ${plural(review, "needs", "need")} review` : ""}.`
          : "No new records were saved.",
        run.mode === "eml_upload"
          ? "Uploaded files aren't kept, so continuing needs the original .eml files again."
          : run.mode === "whatsapp_image"
            ? "Screenshots aren't kept, so send the screenshot again on WhatsApp."
            : run.mode === "whatsapp_voice"
              ? "Voice notes aren't kept, so say it again on WhatsApp."
              : run.mode === "manual_entry"
                ? "Typed entries aren't kept, so add it again."
                : "Retrying re-fetches only the emails that failed; emails already imported are skipped.",
        ...notes,
      ],
      primary: retry ?? continuation ?? { kind: "sources", label: "Back to Sources" },
      secondary: [
        ...(review ? [reviewAction] : []),
        ...(retry && continuation ? [continuation] : []),
        ...(retry || continuation ? [{ kind: "sources", label: "Back to Sources" } as const] : []),
      ],
    };
  }

  if (run.outcome === "partial" || failed > 0) {
    const parts = [
      review ? `${plural(review, "record needs", "records need")} review` : null,
      `${plural(failed, "email", "emails")} couldn't be read`,
    ].filter((part): part is string => part !== null);
    return {
      tone: "attention",
      title: parts.join(" · "),
      detail: [
        created
          ? `${plural(created, "new record was", "new records were")} added.`
          : "No new records were added.",
        review
          ? "Records waiting for review don't change your confirmed totals until you check them."
          : "Your confirmed totals include the new confirmed records.",
        "The emails that couldn't be read are listed below with what you can do about each.",
        ...notes,
      ],
      primary: review ? reviewAction : (retry ?? continuation),
      secondary: [
        ...(review && retry ? [retry] : []),
        ...(continuation && (review || retry) ? [continuation] : []),
      ],
    };
  }

  if (!created && !merged) {
    return {
      tone: "success",
      title: "No new records found",
      detail: [
        `FinBoy checked ${plural(run.candidates_found, "possible money email", "possible money emails")} and found nothing new to add. Your totals are unchanged.`,
        ...notes,
      ],
      primary: continuation ?? { kind: "sources", label: "Back to Sources" },
      secondary: continuation ? [{ kind: "sources", label: "Back to Sources" }] : [],
    };
  }

  if (review) {
    const allNeedReview = review >= created;
    return {
      tone: "attention",
      title: allNeedReview
        ? `${plural(review, "new record needs", "new records need")} review`
        : `${plural(created, "new record", "new records")} added · ${review} need review`,
      detail: [
        allNeedReview
          ? "They don't change your confirmed totals until you check them."
          : "Confirmed records already count toward your overview; the rest wait for your review.",
        ...notes,
      ],
      primary: reviewAction,
      secondary: [...(continuation ? [continuation] : []), { kind: "overview", label: "Go to overview" }],
    };
  }

  return {
    tone: "success",
    title: `${plural(created, "new record", "new records")} added`,
    detail: ["They're confirmed and already count toward your overview.", ...notes],
    primary: continuation ?? { kind: "overview", label: "See your overview" },
    secondary: continuation
      ? [{ kind: "overview", label: "See your overview" }]
      : [{ kind: "sources", label: "Back to Sources" }],
  };
}
