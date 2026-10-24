"use client";

import {
  CircleAlert,
  CircleCheck,
  LoaderCircle,
  RotateCcw,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { outcomeBadges } from "@/components/sources/import-history";
import { UploadStager } from "@/components/sources/upload-stager";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useImportRun } from "@/hooks/use-import-run";
import { useResource } from "@/hooks/use-resource";
import {
  cancelImport,
  continueImport,
  getImportIssues,
  isActive,
  retryImport,
  type ImportIssue,
  type ImportRun,
} from "@/lib/api/imports";
import { formatDayTime, formatRange } from "@/lib/dates";
import { importOutcome, type OutcomeAction } from "@/lib/import-outcome";
import { issueReasonLabels, sourceLabels } from "@/lib/labels";
import { describeProblem, hasCode } from "@/lib/messages";
import { cn } from "@/lib/utils";

const toneIcon = {
  progress: LoaderCircle,
  success: CircleCheck,
  attention: CircleAlert,
  problem: TriangleAlert,
};

function Counters({ run }: { run: ImportRun }) {
  const rows = [
    { label: "Possible money emails found", value: run.candidates_found },
    { label: "Emails checked", value: run.emails_processed },
    { label: "New records added", value: run.transactions_created },
    { label: "Need your review", value: run.needs_review },
    { label: "Duplicates linked to existing records", value: run.duplicates_merged },
    { label: "Not about money (skipped)", value: run.non_financial_skipped },
    { label: "Couldn't be read", value: run.failed },
  ];
  return (
    <dl className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className="flex items-baseline justify-between gap-4 border-b py-2.5 text-sm">
          <dt className="text-ink-soft">{row.label}</dt>
          <dd className="font-semibold tabular-nums">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function IssueList({ run }: { run: ImportRun }) {
  const issues = useResource(`issues:${run.id}:${run.data_version}`, (signal) =>
    getImportIssues(run.id, 0, signal),
  );
  if (issues.status === "loading") return <LoadingPanel className="shadow-none" label="Loading the emails that couldn't be read…" />;
  if (issues.error !== null)
    return (
      <ProblemNotice
        problem={describeProblem(issues.error, "The list of unread emails couldn't be loaded")}
        onRetry={issues.reload}
      />
    );
  if (!issues.data || !issues.data.items.length) return null;
  const groups = new Map<ImportIssue["reason"], ImportIssue[]>();
  for (const issue of issues.data.items) groups.set(issue.reason, [...(groups.get(issue.reason) ?? []), issue]);
  return (
    <div>
      <ul className="space-y-2">
        {[...groups.entries()].map(([reason, items]) => (
          <li key={reason} className="flex items-start justify-between gap-3 rounded-2xl bg-canvas p-3 text-sm">
            <div>
              <p className="font-semibold">{issueReasonLabels[reason]}</p>
              <p className="text-xs text-ink-soft">
                {items.length} {items.length === 1 ? "email" : "emails"} · {sourceLabels[items[0]?.source_mode ?? run.mode]}
                {items.some((item) => item.attempts > 1) && " · tried more than once"}
                {items.every((item) => !item.retryable) && " · can't be retried"}
              </p>
            </div>
          </li>
        ))}
      </ul>
      {issues.data.total > issues.data.items.length && (
        <p className="mt-2 text-xs text-ink-soft">
          Showing {issues.data.items.length} of {issues.data.total}. Retrying handles up to 50 at a time.
        </p>
      )}
      <p className="mt-3 text-xs leading-relaxed text-ink-soft">
        Email contents aren&apos;t kept, so subjects and bodies aren&apos;t shown here. Emails that
        can&apos;t be retried can be skipped safely — nothing else depends on them.
      </p>
    </div>
  );
}

export function ImportResult({ runId }: { runId: string }) {
  const router = useRouter();
  const tracker = useImportRun(runId);
  const action = useAction();
  const [selectingFiles, setSelectingFiles] = useState(false);
  const run = tracker.run;
  const heading = useRef<HTMLHeadingElement>(null);
  const finished = run !== null && !isActive(run);
  const watched = useRef(false);
  useEffect(() => {
    // Move focus to the outcome only when a run the person was watching finishes.
    if (!run) return;
    if (isActive(run)) watched.current = true;
    else if (watched.current) {
      watched.current = false;
      heading.current?.focus();
    }
  }, [run]);

  if (!run) {
    return (
      <div className="space-y-6">
        <PageHeader title="Import results" />
        {tracker.problem ? (
          <ProblemNotice
            problem={
              tracker.problem.kind === "not_found"
                ? { ...tracker.problem, title: "This import couldn't be found", detail: "The link may be old, or the import was removed. Your records weren't changed." }
                : tracker.problem
            }
            onRetry={tracker.refresh}
          >
            <Link href="/sources" className="mt-2 inline-block font-semibold underline underline-offset-4">
              Go to Sources
            </Link>
          </ProblemNotice>
        ) : (
          <LoadingPanel label="Loading this import…" />
        )}
      </div>
    );
  }

  const copy = importOutcome(run);
  const Icon = toneIcon[copy.tone];
  const badge = outcomeBadges[run.outcome];
  const window = formatRange(run.window_start, run.window_end);

  async function perform(item: OutcomeAction) {
    if (!run) return;
    if (item.kind === "review") router.push("/review");
    else if (item.kind === "overview") router.push("/dashboard");
    else if (item.kind === "sources") router.push("/sources");
    else if (item.kind === "select_files") setSelectingFiles(true);
    else if (item.kind === "continue_gmail") {
      const current = run;
      const started = await action.run("continue", "Scanning didn't continue", () =>
        continueImport(current.id, current.data_version),
      );
      if (started) router.push(`/import/${started.import_run_id}`);
    } else {
      const current = run;
      const started = await action.run("retry", "The retry didn't start", async () => {
        try {
          return await retryImport(current.id, current.data_version);
        } catch (error) {
          // Uploaded emails can only be retried from the original files.
          if (!hasCode(error, "original_files_required")) throw error;
          setSelectingFiles(true);
          return null;
        }
      });
      if (started) router.push(`/import/${started.import_run_id}`);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Import results"
        description={`${sourceLabels[run.mode]}${run.started_at ? ` · started ${formatDayTime(run.started_at)}` : ""}${run.finished_at ? ` · finished ${formatDayTime(run.finished_at)}` : ""}`}
        actions={<Badge variant={badge.variant}>{badge.label}</Badge>}
      />

      <section
        aria-labelledby="outcome-title"
        aria-busy={!finished}
        className={cn(
          "rounded-3xl p-5 sm:p-7",
          copy.tone === "problem" ? "border border-amber-200 bg-amber-50" : "surface",
        )}
      >
        <div className="flex items-start gap-3">
          <Icon
            className={cn(
              "mt-1 size-6 shrink-0",
              copy.tone === "progress" && "text-violet-deep motion-safe:animate-spin",
              copy.tone === "success" && "text-positive",
              (copy.tone === "attention" || copy.tone === "problem") && "text-amber-800",
            )}
            aria-hidden="true"
          />
          <div className="min-w-0">
            <h2
              id="outcome-title"
              ref={heading}
              tabIndex={-1}
              className="text-xl font-semibold tracking-tight outline-none sm:text-2xl"
            >
              {copy.title}
            </h2>
            <div role="status" aria-live="polite" className="mt-2 space-y-1.5 text-sm leading-relaxed text-ink-soft">
              {copy.detail.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          </div>
        </div>
        {(copy.primary || copy.secondary.length > 0 || !finished) && (
          <div className="mt-5 flex flex-wrap gap-2">
            {copy.primary && (
              <Button disabled={action.busy !== null} onClick={() => void perform(copy.primary as OutcomeAction)}>
                {copy.primary.kind === "retry_gmail" && <RotateCcw aria-hidden="true" />}
                {action.busy === "retry" && copy.primary.kind === "retry_gmail" ? "Starting retry…" : copy.primary.label}
              </Button>
            )}
            {copy.secondary.map((item) => (
              <Button
                key={item.kind}
                variant="outline"
                disabled={action.busy !== null}
                onClick={() => void perform(item)}
              >
                {item.label}
              </Button>
            ))}
            {!finished && (
              <Button
                variant="outline"
                disabled={run.cancel_requested || action.busy !== null}
                onClick={() =>
                  void action
                    .run("cancel", "The import wasn't cancelled", () => cancelImport(run.id, run.data_version))
                    .then((updated) => updated && tracker.replace(updated))
                }
              >
                {run.cancel_requested ? "Stopping…" : action.busy === "cancel" ? "Cancelling…" : "Cancel import"}
              </Button>
            )}
          </div>
        )}
        {action.problem && <ProblemNotice className="mt-4" problem={action.problem} />}
        {tracker.problem && (
          <ProblemNotice
            className="mt-4"
            problem={{
              ...tracker.problem,
              detail: tracker.retrying
                ? "Showing the last status we received. FinBoy keeps trying automatically and refreshes when you're back online."
                : tracker.problem.detail,
            }}
            onRetry={tracker.refresh}
            retryLabel="Refresh now"
          />
        )}
      </section>

      {selectingFiles && <UploadStager retryCount={run.failed} />}

      {run.failed > 0 && finished && (
        <section aria-labelledby="issues-title" className="surface rounded-3xl p-5 sm:p-6">
          <h2 id="issues-title" className="text-lg font-semibold">
            Emails that couldn&apos;t be read
          </h2>
          <div className="mt-3">
            <IssueList run={run} />
          </div>
        </section>
      )}

      <section aria-labelledby="counts-title" className="surface rounded-3xl p-5 sm:p-6">
        <h2 id="counts-title" className="text-lg font-semibold">
          What happened
        </h2>
        {window && <p className="mt-1 text-sm text-ink-soft">Emails from {window}</p>}
        <div className="mt-3">
          <Counters run={run} />
        </div>
        <p className="mt-4 text-xs leading-relaxed text-ink-soft">
          Based on email-derived records. Records waiting for review aren&apos;t in your totals,
          and your actual bank balance may differ.
        </p>
      </section>
    </div>
  );
}
