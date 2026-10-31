"use client";

import { CircleAlert, CircleCheck, TriangleAlert, Undo2 } from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import {
  getRemovalPreview,
  isActive,
  removeImport,
  type ImportRun,
  type RemovalPreview,
  type StatementSummary,
} from "@/lib/api/imports";
import { formatMoney, rangeMonths } from "@/lib/api/money";
import { formatDay, formatDayTime, formatRange, rangeLabel, type Month } from "@/lib/dates";
import { emitRecordsChanged } from "@/lib/record-events";
import { cn } from "@/lib/utils";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;
const month = (day: string): Month => ({ year: Number(day.slice(0, 4)), month: Number(day.slice(5, 7)) });

/** `?from=2026-04&to=2026-09`: the statement's months, for Reports and records. */
function rangeSearch(statement: StatementSummary) {
  return `from=${statement.period_start.slice(0, 7)}&to=${statement.period_end.slice(0, 7)}`;
}

/** Google's own total beside what FinBoy read from the rows, and whether they match. */
function TotalsCheck({ statement }: { statement: StatementSummary }) {
  const rows = [
    { label: "Paid", google: statement.sent_minor, read: statement.paid_minor },
    { label: "Received", google: statement.received_minor, read: statement.got_minor },
  ];
  return (
    <dl className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
      {rows.map((row) => {
        const matches = row.google === row.read;
        return (
          <div key={row.label} className="rounded-2xl bg-white/60 p-4 ring-1 ring-ink/[0.06]">
            <dt className="text-sm font-medium text-ink-soft">{row.label}</dt>
            <dd className="mt-1 text-xl font-semibold tracking-[-0.02em] tabular-nums">{formatMoney(row.read)}</dd>
            <dd className={cn("mt-1 flex items-center gap-1.5 text-xs font-medium", matches ? "text-positive" : "text-amber-800")}>
              {matches ? <CircleCheck className="size-3.5" aria-hidden="true" /> : <TriangleAlert className="size-3.5" aria-hidden="true" />}
              {matches ? "Matches Google Pay" : `Google Pay says ${formatMoney(row.google)}`}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/** What happened to the rows, in the household's words; zero counts are left out. */
function rowSummary(statement: StatementSummary): string[] {
  const check = statement.possible_duplicates + statement.not_counted;
  return [
    statement.new ? `${plural(statement.new, "new payment", "new payments")} added` : null,
    statement.linked ? `${statement.linked} already in FinBoy from WhatsApp or email, linked instead of added twice` : null,
    statement.already_imported ? `${statement.already_imported} already imported from an earlier statement` : null,
    check ? `${check} to check in To review` : null,
  ].filter((line): line is string => line !== null);
}

function RemoveImport({ run, onRemoved }: { run: ImportRun; onRemoved: (run: ImportRun) => void }) {
  const action = useAction();
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<RemovalPreview | null>(null);

  async function ask() {
    setPreview(null);
    const loaded = await action.run("preview", "This import can't be removed right now", () =>
      getRemovalPreview(run.id),
    );
    if (loaded) {
      setPreview(loaded);
      setOpen(true);
    }
  }

  return (
    <>
      <Button variant="ghost" disabled={action.busy !== null} onClick={() => void ask()}>
        <Undo2 aria-hidden="true" /> {action.busy === "preview" ? "Checking…" : "Remove this import"}
      </Button>
      {action.problem && <ProblemNotice className="mt-3 basis-full" problem={action.problem} />}
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this statement?</AlertDialogTitle>
            <AlertDialogDescription>
              {preview
                ? `${plural(preview.records_removed, "record", "records")} this statement added will be removed, with any changes you made to them.${
                    preview.records_kept
                      ? ` ${plural(preview.records_kept, "record", "records")} that also came from WhatsApp or email stay.`
                      : ""
                  } You can import the statement again later.`
                : "Checking what this statement added…"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={!preview || action.busy !== null}
              onClick={() =>
                preview &&
                void action
                  .run("remove", "The statement wasn't removed", () => removeImport(run.id, preview.data_version))
                  .then((updated) => {
                    if (!updated) return;
                    emitRecordsChanged();
                    onRemoved(updated);
                  })
              }
            >
              {action.busy === "remove" ? "Removing…" : "Remove statement"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

/** The result of one Google Pay statement import, from saving to removal. */
export function StatementResult({
  run,
  onChange,
  problem,
}: {
  run: ImportRun;
  onChange: (run: ImportRun) => void;
  problem: ReactNode;
}) {
  const statement = run.statement;
  const active = isActive(run);
  const removed = Boolean(statement?.removed_at);
  const heading = useRef<HTMLHeadingElement>(null);
  const watched = useRef(false);
  useEffect(() => {
    // Saving takes a few seconds; move focus to the outcome only when the person watched it finish.
    if (active) watched.current = true;
    else if (watched.current) {
      watched.current = false;
      emitRecordsChanged();
      heading.current?.focus();
    }
  }, [active]);

  const period = statement
    ? rangeLabel(month(statement.period_start), month(statement.period_end))
    : formatRange(run.window_start, run.window_end);
  const failed = !active && run.status === "failed";
  const mismatch = failed && statement !== null && !statement.reconciled;
  const tone = active ? "progress" : removed ? "removed" : failed ? "problem" : "success";
  const title = active
    ? "Saving your statement…"
    : removed
      ? "This statement was removed"
      : mismatch
        ? "This statement didn't add up, so nothing was imported"
        : failed
          ? "The statement wasn't saved"
          : `${plural(statement?.rows ?? 0, "payment", "payments")} imported`;
  const check = statement ? statement.possible_duplicates + statement.not_counted : 0;
  const Icon = tone === "problem" ? TriangleAlert : tone === "removed" ? CircleAlert : CircleCheck;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Google Pay statement"
        back={{ href: "/sources", label: "Back to Sources" }}
        description={[period, run.started_at ? `imported ${formatDayTime(run.started_at)}` : null].filter(Boolean).join(" · ")}
        actions={
          <Badge variant={active ? "default" : removed ? "outline" : failed ? "destructive" : "positive"}>
            {active ? "Saving" : removed ? "Removed" : failed ? "Not imported" : "Imported"}
          </Badge>
        }
      />
      <section
        aria-labelledby="statement-outcome"
        aria-busy={active}
        className={cn("rounded-3xl p-5 sm:p-7", tone === "problem" ? "border border-amber-200 bg-amber-50" : "surface")}
      >
        <div className="flex items-start gap-3">
          {active ? (
            <ThinkingOrb state="working" className="-my-1.5 shrink-0" />
          ) : (
            <Icon
              className={cn("mt-1 size-6 shrink-0", tone === "success" ? "text-positive" : tone === "problem" ? "text-amber-800" : "text-ink-soft")}
              aria-hidden="true"
            />
          )}
          <div className="min-w-0">
            <h2 id="statement-outcome" ref={heading} tabIndex={-1} className="text-xl font-semibold tracking-tight outline-none sm:text-2xl">
              {title}
            </h2>
            <div role="status" aria-live="polite" className="mt-2 space-y-1.5 text-sm leading-relaxed text-ink-soft">
              {active && <p>Every row adds up to Google Pay&apos;s own totals. This takes a few seconds.</p>}
              {!active && statement && !failed && !removed && (
                <>
                  <p>
                    {period}
                    {statement.accounts.length > 0 && ` · ${statement.accounts.join(", ")}`}
                  </p>
                  <ul className="space-y-1">
                    {rowSummary(statement).map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </>
              )}
              {removed && statement?.removed_at && (
                <p>
                  Removed {formatDay(statement.removed_at)}. Records only this statement added were taken out; records
                  that also came from WhatsApp or email stayed.
                </p>
              )}
              {mismatch && (
                <p>
                  FinBoy read every page, but the payments it found don&apos;t add up to the totals Google Pay printed,
                  so it saved nothing. Download the statement again and import it once more.
                </p>
              )}
              {failed && !mismatch && <p>Nothing was saved. Choose the PDF again to retry.</p>}
            </div>
          </div>
        </div>

        {statement && !removed && (statement.reconciled || mismatch) && <TotalsCheck statement={statement} />}

        {!active && statement?.holder_matches === false && !removed && (
          <p className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            This statement is for a different phone number than your WhatsApp. Make sure it&apos;s yours — you can
            remove it below.
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-2">
          {statement && !active && !failed && !removed && (
            <>
              <Button asChild>
                <Link href={`/reports?${rangeSearch(statement)}`}>
                  See {plural(rangeMonths({ from: month(statement.period_start), to: month(statement.period_end) }).length, "month", "months")}
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={`/reports?${rangeSearch(statement)}&sort=payees`}>Sort payees</Link>
              </Button>
              {check > 0 && (
                <Button asChild variant="outline">
                  <Link href="/review">Check {check}</Link>
                </Button>
              )}
              <RemoveImport run={run} onRemoved={onChange} />
            </>
          )}
          {(failed || removed) && (
            <Button asChild variant={removed ? "outline" : "default"}>
              <Link href="/sources#statement">{removed ? "Import it again" : "Choose the PDF again"}</Link>
            </Button>
          )}
        </div>
        {problem}
      </section>

      {statement && !failed && !removed && !active && (
        <p className="text-xs leading-relaxed text-ink-soft">
          A Google Pay statement shows payments made in the Google Pay app. Self transfers aren&apos;t in Google&apos;s
          totals{statement.not_counted ? `, so ${plural(statement.not_counted, "self transfer is", "self transfers are")} waiting in To review without counting` : ""}.
        </p>
      )}
    </div>
  );
}
