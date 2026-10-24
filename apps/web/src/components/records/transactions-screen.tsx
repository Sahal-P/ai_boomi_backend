"use client";

import { FileSearch, Inbox, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { EmptyState, LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { RecordDialog } from "@/components/records/record-dialog";
import { RecordFilters } from "@/components/records/record-filters";
import { RecordRow } from "@/components/records/record-row";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { PAGE_SIZE, useRecordList } from "@/hooks/use-record-list";
import { recordsNote } from "@/lib/api/money";
import { monthLabel } from "@/lib/dates";
import { describeProblem, hasCode } from "@/lib/messages";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// Records opened from this list return with Back; deep-linked records close in place.
let openedFromList: string | null = null;

export function TransactionsScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const update = useQueryUpdate();
  const listHeading = useRef<HTMLHeadingElement>(null);
  const { query, list, pinVersion, unpin } = useRecordList("transactions");
  const selectedParam = params.get("selected");
  const selected = selectedParam && UUID.test(selectedParam) ? selectedParam : null;
  const page = list.data;
  const filtered = Boolean(query.q || query.status || query.category || query.kind || query.source);
  const periodLabel =
    query.scope === "all"
      ? "all time"
      : query.period
        ? monthLabel(query.period.year, query.period.month)
        : "this month";
  const versionConflict = list.error !== null && hasCode(list.error, "version_conflict");

  function hrefFor(id: string) {
    const next = new URLSearchParams(params.toString());
    next.set("selected", id);
    return `/transactions?${next.toString()}`;
  }

  function closeRecord() {
    if (selected && openedFromList === selected) {
      openedFromList = null;
      router.back();
    } else update({ selected: null });
  }

  function goTo(offset: number) {
    if (page) pinVersion(page.data_version);
    update({ offset: offset ? String(offset) : null }, "push");
    listHeading.current?.focus();
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Transactions"
        description={recordsNote}
        actions={
          <Button variant="outline" onClick={list.reload} disabled={list.status === "loading" || list.status === "refreshing"}>
            <RefreshCw aria-hidden="true" /> Refresh
          </Button>
        }
      />
      <RecordFilters view="transactions" />

      {query.dataset === "quarantined" && (
        <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950">
          Showing records on hold: they mix sample and household sources, so they don&apos;t count
          toward totals or answers. They&apos;re here for inspection only.{" "}
          <Link href="/transactions" className="font-semibold underline underline-offset-4">
            Back to household records
          </Link>
        </p>
      )}

      <section aria-labelledby="records-heading" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="records-heading" ref={listHeading} tabIndex={-1} className="text-sm font-semibold outline-none">
            {page && !list.stale
              ? page.total === 0
                ? `No records for ${periodLabel}${filtered ? " with these filters" : ""}`
                : `Showing ${page.offset + 1}–${page.offset + page.items.length} of ${page.total} for ${periodLabel}`
              : `Records for ${periodLabel}`}
          </h2>
          {page && page.unresolved_total > 0 && (
            <Link href="/review" className="text-sm font-semibold text-violet-deep underline underline-offset-4">
              {page.unresolved_total} {page.unresolved_total === 1 ? "record needs" : "records need"} review
            </Link>
          )}
        </div>
        <RefreshingLabel active={list.status === "refreshing"}>
          {list.stale ? "Updating for your new filters…" : "Refreshing…"}
        </RefreshingLabel>

        {list.status === "loading" && <LoadingPanel label="Loading records…" />}
        {list.error !== null && (
          <ProblemNotice
            problem={
              versionConflict
                ? {
                    ...describeProblem(list.error, "Your records changed while you were paging"),
                    detail: "Start again from the first page so nothing is skipped or shown twice.",
                  }
                : describeProblem(list.error, page ? "Couldn't refresh the list — showing the last loaded records" : "Records couldn't be loaded")
            }
            onRetry={versionConflict ? () => { unpin(); update({ offset: null }); } : list.reload}
            retryLabel={versionConflict ? "Go to the first page" : "Try again"}
          />
        )}

        {page && page.items.length === 0 && !list.stale && (
          filtered ? (
            <EmptyState
              icon={FileSearch}
              title="No records match these filters"
              actions={
                <Button variant="outline" onClick={() => update({ q: null, status: null, category: null, kind: null, source: null, offset: null })}>
                  Clear filters
                </Button>
              }
            >
              Try another search or period. {page.unresolved_total > 0 && `${page.unresolved_total} records still need review.`}
            </EmptyState>
          ) : (
            <EmptyState
              icon={Inbox}
              title={`No records for ${periodLabel}`}
              actions={
                <>
                  <Button asChild variant="outline">
                    <Link href="/transactions?scope=all">See all time</Link>
                  </Button>
                  <Button asChild variant="ghost">
                    <Link href="/sources">Go to Sources</Link>
                  </Button>
                </>
              }
            >
              Nothing was found in this period. Scan Gmail or upload emails to add records.
            </EmptyState>
          )
        )}

        {page && page.items.length > 0 && (
          <div className={list.stale ? "opacity-60 transition-opacity" : undefined} aria-busy={list.status === "refreshing"}>
            <ul className="surface divide-y overflow-hidden rounded-3xl">
              {page.items.map((row) => (
                <li key={row.id} onClickCapture={() => { openedFromList = row.id; }}>
                  <RecordRow row={row} href={hrefFor(row.id)} selected={row.id === selected} />
                </li>
              ))}
            </ul>
          </div>
        )}

        {page && !list.stale && (page.offset > 0 || page.next_offset !== null) && (
          <nav aria-label="Pages" className="flex items-center justify-between gap-3">
            <Button variant="outline" disabled={page.offset === 0} onClick={() => goTo(Math.max(0, page.offset - PAGE_SIZE))}>
              Previous {PAGE_SIZE}
            </Button>
            <p className="text-xs text-ink-soft">
              Page {Math.floor(page.offset / PAGE_SIZE) + 1} of {Math.max(1, Math.ceil(page.total / PAGE_SIZE))}
            </p>
            <Button variant="outline" disabled={page.next_offset === null} onClick={() => page.next_offset !== null && goTo(page.next_offset)}>
              Next {PAGE_SIZE}
            </Button>
          </nav>
        )}
      </section>

      <RecordDialog
        id={selected}
        onClose={closeRecord}
        onDecided={() => list.reload()}
        focusFallback={() => listHeading.current}
      />
    </div>
  );
}
