"use client";

import { ChevronLeft, ChevronRight, CircleCheckBig, FileSearch, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { EmptyState, LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { RecordDecision } from "@/components/records/record-decision";
import { RecordDialog } from "@/components/records/record-dialog";
import { RecordFilters } from "@/components/records/record-filters";
import { RecordRow } from "@/components/records/record-row";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useQueryUpdate } from "@/hooks/use-query-update";
import type { DecisionOutcome } from "@/hooks/use-record";
import { PAGE_SIZE, useRecordList } from "@/hooks/use-record-list";
import { recordOutcome } from "@/lib/api/privacy";
import { undoDecision } from "@/lib/api/transactions";
import { describeProblem, hasCode } from "@/lib/messages";
import { shortcutsEnabled, typingTarget } from "@/lib/shortcuts";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const verbs: Record<string, string> = {
  confirm: "Confirmed",
  reject: "Rejected",
  merge: "Merged",
  "keep-separate": "Kept separate",
  correct: "Saved",
  reopen: "Reopened",
};

/** An attention queue: every unresolved record (any month), one decision at a time. */
export function ReviewScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const wide = useMediaQuery("(min-width: 64rem)");
  const { query, list, pinVersion, unpin } = useRecordList("review");
  const queueHeading = useRef<HTMLHeadingElement>(null);
  const [focusPanel, setFocusPanel] = useState(false);
  const [decided, setDecided] = useState(0);
  const [last, setLast] = useState<{ outcome: DecisionOutcome; recordId: string } | null>(null);
  const undo = useAction();
  const page = list.stale ? null : list.data;
  const items = useMemo(() => page?.items ?? [], [page]);
  const selectedParam = params.get("selected");
  const selected = selectedParam && UUID.test(selectedParam) ? selectedParam : null;
  const activeId = selected ?? (wide ? (items[0]?.id ?? null) : null);
  const position = activeId ? items.findIndex((item) => item.id === activeId) : -1;
  const filtered = Boolean(query.q || query.category || query.kind || query.source || query.period);
  const versionConflict = list.error !== null && hasCode(list.error, "version_conflict");

  function select(id: string | null) {
    update({ selected: id });
  }

  function hrefFor(id: string) {
    const next = new URLSearchParams(params.toString());
    next.set("selected", id);
    return `/review?${next.toString()}`;
  }

  function focusRow(id: string) {
    requestAnimationFrame(() =>
      document.querySelector<HTMLElement>(`[data-review-queue] [data-record-id="${CSS.escape(id)}"]`)?.focus(),
    );
  }

  function step(delta: number) {
    const next = items[position + delta];
    if (next) select(next.id);
  }

  // Keep the shortcut handler in sync before the new queue position is painted.
  // A second key can otherwise reach the previous position's passive-effect listener.
  useLayoutEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || typingTarget(event.target)) return;
      if (document.querySelector("[role=dialog][data-state=open], [role=alertdialog]") && wide) return;
      const forward = event.key === "j" || event.key === "ArrowDown";
      const back = event.key === "k" || event.key === "ArrowUp";
      if (!(forward || back) || !shortcutsEnabled()) return;
      if ((event.key === "ArrowDown" || event.key === "ArrowUp") && !(event.target instanceof HTMLElement && event.target.closest("[data-review-queue]"))) return;
      event.preventDefault();
      const next = items[(position === -1 ? (forward ? -1 : items.length) : position) + (forward ? 1 : -1)];
      if (!next) return;
      setFocusPanel(false);
      update({ selected: next.id });
      focusRow(next.id);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, position, update, wide]);

  const measuredDecision = useRef<string | null>(null);
  useEffect(() => {
    if (last && page?.unresolved_total === 0 && measuredDecision.current !== last.outcome.result.decision_id) {
      measuredDecision.current = last.outcome.result.decision_id;
      recordOutcome("review_completed");
    }
  }, [last, page]);

  function onDecided(outcome: DecisionOutcome, recordId: string) {
    setDecided((value) => value + 1);
    setLast({ outcome, recordId });
    if (outcome.action === "correct") return;
    // The decided record leaves the queue: move on to the next one, keeping the undo bar.
    const next = items[position + 1] ?? items[position - 1] ?? null;
    select(next ? next.id : null);
    list.reload();
    if (next) setFocusPanel(true);
    else requestAnimationFrame(() => queueHeading.current?.focus());
  }

  async function undoLast() {
    if (!last) return;
    const done = await undo.run("undo", "That decision wasn't undone", () =>
      undoDecision(last.recordId, last.outcome.result.decision_id, last.outcome.result.detail.version),
    );
    if (done) {
      setLast(null);
      list.reload();
      select(last.recordId);
    }
  }

  const empty = page && page.items.length === 0;
  const undoBar = (
    <div role="status" aria-live="polite">
      {last && last.outcome.action !== "correct" && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-ink px-4 py-2.5 text-sm text-white">
          <span>
            {verbs[last.outcome.action] ?? "Decided"}: <span className="font-semibold">{last.outcome.merchant}</span>
          </span>
          <Button size="sm" className="bg-white text-ink hover:bg-white/85" disabled={undo.busy !== null} onClick={() => void undoLast()}>
            {undo.busy ? "Undoing…" : "Undo"}
          </Button>
          <button
            type="button"
            className="ml-auto min-h-11 px-2 text-xs font-semibold text-white/85 underline underline-offset-4"
            onClick={() => setLast(null)}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Review"
        description="Records FinBoy isn't sure about. They stay out of your totals until you decide."
        actions={
          <Button variant="outline" onClick={list.reload} disabled={list.status === "loading" || list.status === "refreshing"}>
            <RefreshCw aria-hidden="true" /> Refresh
          </Button>
        }
      />
      <RecordFilters view="review" />

      {!(wide && activeId) && !(!wide && selected) && undoBar}
      {undo.problem && <ProblemNotice problem={undo.problem} />}

      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 ref={queueHeading} tabIndex={-1} className="text-base font-semibold outline-none">
          {page
            ? page.unresolved_total === 0
              ? "Nothing needs review"
              : `${page.unresolved_total} ${page.unresolved_total === 1 ? "record needs" : "records need"} review`
            : "Records to review"}
          {page && filtered && page.unresolved_total > 0 && (
            <span className="font-normal text-ink-soft"> · {page.total} match your filters</span>
          )}
        </h2>
        {decided > 0 && <p className="text-xs text-ink-soft">You&apos;ve decided {decided} this visit.</p>}
      </div>
      <RefreshingLabel active={list.status === "refreshing"}>Updating the queue…</RefreshingLabel>
      {list.status === "loading" && <LoadingPanel label="Loading records to review…" />}
      {list.error !== null && (
        <ProblemNotice
          problem={
            versionConflict
              ? { ...describeProblem(list.error, "The queue changed while you were paging"), detail: "Start from the first page so nothing is skipped." }
              : describeProblem(list.error, list.data ? "Couldn't refresh the queue — showing the last loaded records" : "The review queue couldn't be loaded")
          }
          onRetry={versionConflict ? () => { unpin(); update({ offset: null }); } : list.reload}
          retryLabel={versionConflict ? "Go to the first page" : "Try again"}
        />
      )}

      {empty && (page.unresolved_total > 0 ? (
        <EmptyState
          icon={FileSearch}
          title="No records match these filters"
          actions={
            <Button variant="outline" onClick={() => update({ q: null, category: null, kind: null, source: null, year: null, month: null, offset: null })}>
              Clear filters
            </Button>
          }
        >
          {page.unresolved_total} {page.unresolved_total === 1 ? "record still needs" : "records still need"} review — they&apos;re just hidden by your search or filters.
        </EmptyState>
      ) : (
        <EmptyState
          icon={CircleCheckBig}
          title="You're all caught up"
          actions={
            <>
              <Button asChild>
                <Link href="/dashboard">See your overview</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link href="/transactions">All transactions</Link>
              </Button>
            </>
          }
        >
          Every record has a decision. New imports may add more; they&apos;ll appear here.
        </EmptyState>
      ))}

      {items.length > 0 && (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <div
            data-review-queue
            className={list.status === "refreshing" ? "opacity-70" : undefined}
            onClickCapture={() => setFocusPanel(true)}
          >
            <ul aria-label="Records to review" className="surface divide-y overflow-hidden rounded-3xl">
              {items.map((row) => (
                <li key={row.id}>
                  <RecordRow
                    row={row}
                    href={hrefFor(row.id)}
                    replace
                    compact
                    selected={row.id === activeId}
                  />
                </li>
              ))}
            </ul>
            {page && (page.offset > 0 || page.next_offset !== null) && (
              <nav aria-label="Queue pages" className="mt-3 flex items-center justify-between gap-2">
                <Button variant="ghost" size="sm" disabled={page.offset === 0} onClick={() => { pinVersion(page.data_version); update({ offset: page.offset - PAGE_SIZE > 0 ? String(page.offset - PAGE_SIZE) : null, selected: null }); }}>
                  Previous
                </Button>
                <p className="text-xs text-ink-soft">
                  {page.offset + 1}–{page.offset + page.items.length} of {page.total}
                </p>
                <Button variant="ghost" size="sm" disabled={page.next_offset === null} onClick={() => { if (page.next_offset === null) return; pinVersion(page.data_version); update({ offset: String(page.next_offset), selected: null }); }}>
                  Next
                </Button>
              </nav>
            )}
          </div>

          {wide && activeId && (
            <section aria-label="Decision" className="surface rounded-3xl p-5 lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto sm:p-6">
              {undoBar}
              <div className="mb-4 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-ink-soft">
                  {position >= 0 ? `${page ? page.offset + position + 1 : position + 1} of ${page?.total ?? items.length}` : "Selected record"}
                </p>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" disabled={position <= 0} onClick={() => step(-1)} aria-label="Previous record">
                    <ChevronLeft aria-hidden="true" /> Previous
                  </Button>
                  <Button variant="ghost" size="sm" disabled={position === -1 || position >= items.length - 1} onClick={() => step(1)} aria-label="Next record">
                    Next <ChevronRight aria-hidden="true" />
                  </Button>
                </div>
              </div>
              <RecordDecision
                key={activeId}
                id={activeId}
                focusOnLoad={focusPanel}
                showUndo={false}
                onDecided={(outcome) => onDecided(outcome, activeId)}
              />
            </section>
          )}
        </div>
      )}

      {!wide && (
        <RecordDialog
          id={selected}
          onClose={() => select(null)}
          onDecided={(outcome) => selected && onDecided(outcome, selected)}
          focusFallback={() => queueHeading.current}
          header={selected ? undoBar : null}
          showUndo={false}
          footer={
            items.length > 1 && position >= 0 ? (
              <div className="mt-6 flex items-center justify-between gap-2 border-t pt-4">
                <Button variant="outline" disabled={position <= 0} onClick={() => step(-1)}>
                  <ChevronLeft aria-hidden="true" /> Previous
                </Button>
                <span className="text-xs text-ink-soft">{position + 1} of {items.length}</span>
                <Button variant="outline" disabled={position >= items.length - 1} onClick={() => step(1)}>
                  Next <ChevronRight aria-hidden="true" />
                </Button>
              </div>
            ) : null
          }
        />
      )}
    </div>
  );
}
