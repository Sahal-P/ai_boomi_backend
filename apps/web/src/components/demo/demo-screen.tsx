"use client";

import { ArrowRight, Eye, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Dialog } from "radix-ui";
import { Brand } from "@/components/brand";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { RecordAmount, RecordGlyph } from "@/components/records/record-bits";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useResource } from "@/hooks/use-resource";
import { getDemo, type DemoData } from "@/lib/api/demo";
import { formatMoney, recordsNote, type Transaction } from "@/lib/api/money";
import { formatDay } from "@/lib/dates";
import {
  categoryLabels,
  effectLabel,
  extractionLabels,
  kindLabels,
  liabilityLabels,
  obligationKindLabels,
  paymentLabels,
  reasonFor,
  statusLabels,
} from "@/lib/labels";
import { describeProblem } from "@/lib/messages";

function SampleTag() {
  return (
    <span className="rounded-full bg-sunflower px-2 py-0.5 text-[11px] font-semibold text-ink ring-1 ring-ink/15">Sample</span>
  );
}

function SampleRecord({ row, onClose }: { row: Transaction | null; onClose: () => void }) {
  const reason = row ? reasonFor(row) : null;
  return (
    <Dialog.Root open={row !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/20 backdrop-blur-sm" />
        <Dialog.Content
          aria-describedby={undefined}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (row) document.querySelector<HTMLElement>(`[data-sample-id="${CSS.escape(row.id)}"]`)?.focus();
          }}
          className="fixed inset-x-0 bottom-0 z-50 max-h-[90dvh] overflow-y-auto rounded-t-3xl float-panel p-5 pb-8 sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:w-[calc(100%-2rem)] sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:p-7"
        >
          {row && (
            <>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <SampleTag />
                  <Dialog.Title className="mt-2 text-xl font-semibold">{row.merchant}</Dialog.Title>
                </div>
                <Dialog.Close asChild>
                  <Button variant="ghost" size="icon" aria-label="Close sample record">
                    <X className="size-5" aria-hidden="true" />
                  </Button>
                </Dialog.Close>
              </div>
              <p className="mt-2 text-2xl font-semibold"><RecordAmount row={row} /></p>
              <p className="mt-1 text-sm text-ink-soft">
                {kindLabels[row.kind]} · {categoryLabels[row.category]} · {formatDay(row.occurred_at)} · {statusLabels[row.status]}
              </p>
              {reason && (
                <p className="mt-4 rounded-2xl bg-amber-50 p-4 text-sm text-amber-950">
                  <span className="font-semibold">{reason.title}.</span> {reason.detail}
                </p>
              )}
              <dl className="mt-4 space-y-2 text-sm">
                <div><dt className="text-xs text-ink-soft">Payment</dt><dd>{paymentLabels[row.payment_verification]}</dd></div>
                <div><dt className="text-xs text-ink-soft">Details in the email</dt><dd>{extractionLabels[row.extraction_quality]}</dd></div>
                <div><dt className="text-xs text-ink-soft">Effect on totals</dt><dd>{effectLabel(row)}</dd></div>
              </dl>
              <p className="mt-5 text-xs leading-relaxed text-ink-soft">
                This synthetic record is part of the read-only sample. In your household, you&apos;d
                see its source emails and could confirm, correct or reject it.
              </p>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function DemoBody({ demo }: { demo: DemoData }) {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const selected = demo.transactions.find((row) => row.id === params.get("selected")) ?? null;
  const { summary } = demo;
  return (
    <div className="space-y-5">
      <section aria-labelledby="sample-estimate" className="solid-hero rounded-3xl p-5 sm:p-8">
        <div className="flex flex-wrap items-center gap-2"><SampleTag /><span className="text-xs text-sunflower-ink">as of {formatDay(demo.as_of)}</span></div>
        <h2 id="sample-estimate" className="mt-3 text-sm font-medium text-sunflower-ink">Estimated unallocated (sample)</h2>
        <p className="mt-2 text-[2.75rem] leading-none font-semibold tracking-[-0.04em] tabular-nums sm:text-6xl">{formatMoney(summary.estimated_unallocated_minor)}</p>
        <dl className="mt-5 grid gap-2 text-sm sm:grid-cols-3">
          <div className="rounded-2xl bg-white/55 p-3"><dt className="text-sunflower-ink">Tracked income</dt><dd className="mt-1 font-semibold tabular-nums">+ {formatMoney(summary.tracked_income_minor)}</dd></div>
          <div className="rounded-2xl bg-white/55 p-3"><dt className="text-sunflower-ink">Confirmed net outflows</dt><dd className="mt-1 font-semibold tabular-nums">− {formatMoney(summary.confirmed_outflows_minor)}</dd></div>
          <div className="rounded-2xl bg-white/55 p-3"><dt className="text-sunflower-ink">Unresolved obligations</dt><dd className="mt-1 font-semibold tabular-nums">− {formatMoney(summary.unresolved_commitments_minor)}</dd></div>
        </dl>
        <p className="mt-4 text-sm text-sunflower-ink">
          {summary.pending_review_count} sample records wait for review and aren&apos;t counted. {recordsNote}
        </p>
      </section>

      <div className="grid items-start gap-5 xl:grid-cols-[1.3fr_1fr]">
        <section aria-labelledby="sample-records" className="surface rounded-3xl p-2 sm:p-3">
          <h2 id="sample-records" className="px-3 pt-3 text-lg font-semibold">Sample records</h2>
          <ul className="mt-2 divide-y">
            {demo.transactions.map((row) => {
              const reason = reasonFor(row);
              return (
                <li key={row.id}>
                  <button
                    type="button"
                    data-sample-id={row.id}
                    onClick={() => update({ selected: row.id }, "push")}
                    className="flex w-full items-start gap-3 rounded-2xl px-3 py-3 text-left hover:bg-white/60"
                  >
                    <RecordGlyph row={row} />
                    <span className="min-w-0 flex-1">
                      {reason && <span className="block text-xs font-semibold text-amber-900">{reason.title}</span>}
                      <span className="block text-sm font-semibold">{row.merchant}</span>
                      <span className="block text-xs text-ink-soft">{kindLabels[row.kind]} · {formatDay(row.occurred_at)}</span>
                    </span>
                    <span className="shrink-0 text-right">
                      <RecordAmount row={row} className="block text-sm font-semibold" />
                      <SampleTag />
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
        <div className="space-y-5">
          <section aria-labelledby="sample-categories" className="surface rounded-3xl p-5">
            <h2 id="sample-categories" className="text-lg font-semibold">Where it went (sample)</h2>
            <ul className="mt-3 space-y-2 text-sm">
              {summary.categories.filter((item) => item.amount_minor !== 0).map((item) => (
                <li key={item.category} className="flex justify-between gap-3">
                  <span>{categoryLabels[item.category]}</span>
                  <span className="font-semibold tabular-nums">{item.amount_minor < 0 ? `Net refund ${formatMoney(-item.amount_minor)}` : formatMoney(item.amount_minor)}</span>
                </li>
              ))}
            </ul>
          </section>
          <section aria-labelledby="sample-obligations" className="surface rounded-3xl p-5">
            <h2 id="sample-obligations" className="text-lg font-semibold">Bills (sample)</h2>
            <ul className="mt-3 divide-y text-sm">
              {demo.commitments.map((item) => (
                <li key={item.id} className="flex justify-between gap-3 py-2">
                  <span>
                    <span className="block font-medium">{item.label}</span>
                    <span className="block text-xs text-ink-soft">{obligationKindLabels[item.kind]} · {liabilityLabels[item.liability_state]} {formatDay(item.due_date)}</span>
                  </span>
                  <span className="font-semibold tabular-nums">{formatMoney(item.amount_minor)}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
      <SampleRecord row={selected} onClose={() => update({ selected: null })} />
    </div>
  );
}

/** A read-only synthetic household, visibly separate from yours. It never writes anything. */
export function DemoScreen() {
  const demo = useResource("demo", (signal) => getDemo(signal));
  return (
    <div className="bg-field min-h-dvh">
      {/* Content scrolls under the sample banner, so it is blurred near-opaque glass. */}
      <header className="sticky top-0 z-40 border-b border-white/70 bg-white/85 shadow-hairline backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-8">
          <div className="flex items-center gap-3">
            <Brand />
            <span className="flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-xs font-semibold text-white">
              <Eye className="size-3.5" aria-hidden="true" /> Sample data · read-only
            </span>
          </div>
          <Button asChild size="sm">
            <Link href="/sources?intent=gmail">
              Use your own emails <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-8 sm:py-10">
        <div>
          <h1 className="text-[1.75rem] leading-tight font-medium tracking-[-0.025em] sm:text-[2rem]">A sample household</h1>
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink-soft">
            Arun&apos;s synthetic mailbox, shown the way FinBoy shows yours. Nothing here comes from
            or changes your household records, and leaving the sample changes nothing.
          </p>
        </div>
        {demo.status === "loading" && <LoadingPanel label="Loading the sample…" />}
        {demo.error !== null && (
          <ProblemNotice problem={describeProblem(demo.error, "The sample couldn't be loaded")} onRetry={demo.reload} />
        )}
        {demo.data && <DemoBody demo={demo.data} />}
      </main>
    </div>
  );
}
