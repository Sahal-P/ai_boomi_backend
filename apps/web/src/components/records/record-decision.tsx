"use client";

import { BadgeCheck, CircleAlert, GitMerge, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { CorrectionForm, type FormSubmit } from "@/components/records/correction-form";
import { MergePanel } from "@/components/records/merge-panel";
import { RecordAmount, SourceTags } from "@/components/records/record-bits";
import { RecordEvidence } from "@/components/records/record-evidence";
import { RecordHistory } from "@/components/records/record-history";
import { Button } from "@/components/ui/button";
import { useRecord, type DecisionOutcome } from "@/hooks/use-record";
import type { DecisionRequest } from "@/lib/api/transactions";
import { formatDayTime } from "@/lib/dates";
import {
  categoryLabels,
  effectLabel,
  extractionLabel,
  kindLabels,
  paymentLabel,
  reasonFor,
  screenshotOnly,
  voiceOnly,
  statusLabels,
} from "@/lib/labels";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const doneCopy: Record<DecisionRequest["action"], string> = {
  confirm: "Confirmed. It now counts toward your totals.",
  reject: "Rejected. It won't count toward your totals.",
  reopen: "Reopened. It's back in the review queue.",
  correct: "Saved. Your correction is recorded in the history.",
  merge: "Merged. The match now carries both source notifications.",
  "keep-separate": "Kept as its own record.",
};

/**
 * The decision surface for one record: why it needs attention, the decisive evidence, the
 * relevant actions only, and recovery through version-checked undo/reopen.
 */
export function RecordDecision({
  id,
  focusOnLoad = false,
  onDecided,
  onDirtyChange,
  showUndo = true,
}: {
  id: string;
  /** Move focus to the record's heading once its evidence has loaded. */
  focusOnLoad?: boolean;
  onDecided?: (outcome: DecisionOutcome) => void;
  onDirtyChange?: (dirty: boolean) => void;
  showUndo?: boolean;
}) {
  const record = useRecord(id);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [dirty, setDirty] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [last, setLast] = useState<{ decisionId: string; action: DecisionRequest["action"] } | null>(null);
  const handleDirty = useCallback(
    (value: boolean) => {
      setDirty(value);
      onDirtyChange?.(value);
    },
    [onDirtyChange],
  );
  const detail = record.detail.stale ? null : record.detail.data;
  const loadedId = detail?.transaction.id;
  useEffect(() => {
    if (focusOnLoad && loadedId) headingRef.current?.focus();
  }, [focusOnLoad, loadedId]);

  const decideWith = useCallback(
    async (request: DecisionRequest, failureTitle: string) => {
      setMessage(null);
      const outcome = await record.submit(request, failureTitle);
      if (!outcome) return false;
      setLast({ decisionId: outcome.result.decision_id, action: request.action });
      setMessage(doneCopy[request.action]);
      setComparing(false);
      onDecided?.(outcome);
      return true;
    },
    [record, onDecided],
  );

  if (!detail) {
    if (record.detail.error !== null) {
      const problem = describeProblem(record.detail.error, "This record couldn't be loaded");
      return (
        <ProblemNotice
          problem={
            problem.kind === "not_found"
              ? {
                  ...problem,
                  detail:
                    "It may have been merged or removed, or the link points to sample data. Nothing changed.",
                }
              : problem
          }
          onRetry={problem.kind === "not_found" ? undefined : record.detail.reload}
        />
      );
    }
    return <LoadingPanel className="shadow-none" label="Loading the record and its evidence…" />;
  }

  const tx = detail.transaction;
  const reason = reasonFor(tx);
  const needsReview = tx.status === "needs_review";
  const quarantined = tx.dataset === "quarantined";
  const editable = !quarantined && (needsReview || tx.status === "confirmed");
  const duplicate = tx.review_reason === "possible_duplicate";
  const busy = record.busy !== null;
  const conflict = record.problem?.kind === "conflict";

  const onSubmit: FormSubmit = (intent, correction) => {
    const withCorrection = Object.keys(correction).length ? { correction } : {};
    return intent === "save_confirm"
      ? decideWith(
          { expected_version: detail.version, action: "confirm", ...withCorrection },
          "The record wasn't confirmed",
        )
      : decideWith(
          { expected_version: detail.version, action: "correct", correction },
          "Your correction wasn't saved",
        );
  };

  return (
    <article aria-labelledby={`record-${tx.id}`} className="space-y-5">
      <header>
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-semibold",
              needsReview ? "bg-amber-50 text-amber-900" : tx.status === "confirmed" ? "bg-emerald-50 text-positive" : "bg-muted text-ink-soft",
            )}
          >
            {statusLabels[tx.status]}
          </span>
          <SourceTags row={tx} />
        </div>
        <h2
          id={`record-${tx.id}`}
          ref={headingRef}
          tabIndex={-1}
          className="mt-2 text-xl font-semibold tracking-tight break-words outline-none"
        >
          {tx.merchant}
        </h2>
        <p className="mt-1 text-2xl font-semibold tracking-tight">
          <RecordAmount row={tx} />
        </p>
        <p className="mt-1 text-sm text-ink-soft">
          {kindLabels[tx.kind]} · {categoryLabels[tx.category]} · {formatDayTime(tx.occurred_at)}
        </p>
        <p className="mt-1 text-xs font-medium text-ink-soft">{effectLabel(tx)}</p>
      </header>

      {reason && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950">
          <p className="flex items-center gap-2 font-semibold">
            <CircleAlert className="size-4 text-amber-800" aria-hidden="true" /> {reason.title}
          </p>
          <p className="mt-1">{reason.detail}</p>
          <p className="mt-1">
            <span className="font-semibold">To resolve:</span> {reason.resolve}
          </p>
        </div>
      )}

      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <div className="rounded-2xl bg-canvas p-3">
          <dt className="text-xs text-ink-soft">Payment</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 font-medium">
            {tx.payment_verification === "verified" && <BadgeCheck className="size-4 text-positive" aria-hidden="true" />}
            {paymentLabel(tx)}
          </dd>
        </div>
        <div className="rounded-2xl bg-canvas p-3">
          <dt className="text-xs text-ink-soft">
            {screenshotOnly(tx) ? "Details in the screenshot" : voiceOnly(tx) ? "Details in your voice note" : "Details in the email"}
          </dt>
          <dd className="mt-0.5 font-medium">{extractionLabel(tx)}</dd>
        </div>
      </dl>

      {quarantined && (
        <p className="flex gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-amber-800" aria-hidden="true" />
          This record mixes sample and household sources, so it&apos;s on hold: it doesn&apos;t count
          toward totals or answers and can only be inspected until it&apos;s repaired.
        </p>
      )}
      {tx.status === "merged" && tx.merged_into_id && (
        <p className="text-sm">
          This record was merged into{" "}
          <Link href={`/transactions?selected=${tx.merged_into_id}`} className="font-semibold text-violet-deep underline underline-offset-4">
            the record that kept its evidence
          </Link>
          . Undo the merge from the history below if it was a mistake.
        </p>
      )}

      {needsReview && !quarantined && (duplicate || comparing) && (
        <MergePanel tx={tx} version={detail.version} busy={busy || dirty} onDecide={decideWith} />
      )}

      <section aria-labelledby={`decide-${tx.id}`} className="space-y-3">
        <h3 id={`decide-${tx.id}`} className="font-semibold">
          {needsReview ? "Your decision" : editable ? "Correct this record" : "Details"}
        </h3>
        <CorrectionForm
          key={tx.id}
          tx={tx}
          editable={editable}
          canConfirm={needsReview && !quarantined}
          busy={busy}
          onSubmit={onSubmit}
          onDirtyChange={handleDirty}
        />
        {needsReview && !quarantined && (
          <div className="flex flex-wrap items-center gap-2 border-t pt-3">
            <Button
              variant="destructive"
              disabled={busy || dirty}
              onClick={() => void decideWith({ expected_version: detail.version, action: "reject" }, "The record wasn't rejected")}
            >
              {record.busy === "reject" ? "Rejecting…" : "Reject — not a real payment"}
            </Button>
            {!duplicate && !comparing && (
              <Button variant="ghost" disabled={busy} onClick={() => setComparing(true)}>
                <GitMerge aria-hidden="true" /> It&apos;s a duplicate…
              </Button>
            )}
            {dirty && <p className="w-full text-xs text-ink-soft">Save or discard your edits before rejecting.</p>}
          </div>
        )}
        {tx.status === "rejected" && !quarantined && (
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => void decideWith({ expected_version: detail.version, action: "reopen" }, "The record wasn't reopened")}
          >
            Reopen for review
          </Button>
        )}
      </section>

      {record.problem && (
        <ProblemNotice
          problem={record.problem}
          onRetry={conflict ? () => { record.clearProblem(); record.detail.reload(); } : undefined}
          retryLabel="Load the latest version"
        >
          {conflict && dirty && <p className="mt-1">Your unsaved edits stay in the form so you can re-check them.</p>}
        </ProblemNotice>
      )}
      <div role="status" aria-live="polite" className="text-sm font-medium">
        {message && (
          <p className="flex flex-wrap items-center gap-3 rounded-2xl bg-lilac/60 px-4 py-3 text-ink">
            {message}
            {showUndo && last && detail.decisions.some((item) => item.id === last.decisionId && item.can_undo && !item.undone_at) && (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() =>
                  void record.undo(last.decisionId, detail.version).then((result) => {
                    if (result) {
                      setMessage("Undone. The record is back the way it was.");
                      setLast(null);
                    }
                  })
                }
              >
                Undo
              </Button>
            )}
          </p>
        )}
      </div>

      <RecordEvidence detail={detail} />
      <RecordHistory
        detail={detail}
        busy={busy}
        onUndo={(decisionId) =>
          void record.undo(decisionId, detail.version).then((result) => {
            if (result) setMessage("Undone. The record is back the way it was.");
          })
        }
      />
    </article>
  );
}
