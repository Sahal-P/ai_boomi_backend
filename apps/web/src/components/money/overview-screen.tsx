"use client";

import {
  ArrowRight,
  CalendarClock,
  ChevronRight,
  CircleAlert,
  Inbox,
  ListChecks,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { EmptyState, LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { ObligationDialog } from "@/components/money/obligation-dialog";
import { SimulationPanel } from "@/components/money/simulation-panel";
import { coverageHeadline } from "@/components/sources/coverage-summary";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useResource } from "@/hooks/use-resource";
import { formatMoney, getObligations, getSummary, recordsNote, type MoneySummary, type Period } from "@/lib/api/money";
import { recordOutcome } from "@/lib/api/privacy";
import { formatDay, formatDayTime, formatRange, istDate, monthLabel } from "@/lib/dates";
import { categoryLabels, liabilityLabels, obligationKindLabels } from "@/lib/labels";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

function readPeriod(params: URLSearchParams): Period {
  const year = Number(params.get("year"));
  const month = Number(params.get("month"));
  return Number.isInteger(year) && year >= 2000 && year <= 2100 && Number.isInteger(month) && month >= 1 && month <= 12
    ? { year, month }
    : null;
}

function periodParams(period: Period) {
  return period ? `&year=${period.year}&month=${period.month}` : "";
}

function Exceptions({ summary, period }: { summary: MoneySummary; period: Period }) {
  const { coverage } = summary;
  const items: { key: string; href: string; icon: typeof Inbox; text: string }[] = [];
  if (coverage.pending_review_count > 0) {
    items.push({
      key: "review",
      href: "/review",
      icon: ListChecks,
      text: `${plural(coverage.pending_review_count, "record waits", "records wait")} for review and ${coverage.pending_review_count === 1 ? "isn't" : "aren't"} in these totals`,
    });
  }
  if (summary.overdue_commitment_count > 0) {
    items.push({
      key: "overdue",
      href: "#obligations",
      icon: CalendarClock,
      text: `${plural(summary.overdue_commitment_count, "overdue obligation", "overdue obligations")} (${formatMoney(summary.overdue_commitments_minor)}) still deducted`,
    });
  }
  if (coverage.failed_source_count > 0) {
    items.push({
      key: "failed",
      href: coverage.active_import_id ? `/import/${coverage.active_import_id}` : "/sources",
      icon: CircleAlert,
      text: `${plural(coverage.failed_source_count, "email", "emails")} couldn't be read`,
    });
  }
  if (coverage.state === "unknown" || coverage.truncated) {
    items.push({
      key: "coverage",
      href: "/sources",
      icon: Inbox,
      text: coverage.state === "unknown" ? "Coverage unknown — no completed scan yet" : "The last scan stopped at its limit",
    });
  }
  if (coverage.quarantined_count > 0) {
    items.push({
      key: "hold",
      href: "/transactions?dataset=quarantined&scope=all",
      icon: ShieldAlert,
      text: `${plural(coverage.quarantined_count, "record is", "records are")} on hold and excluded`,
    });
  }
  if (!items.length) return null;
  return (
    <section aria-label="Needs your attention">
      <ul className="grid gap-2 sm:grid-cols-2">
        {items.map(({ key, href, icon: Icon, text }) => (
          <li key={key}>
            <Link
              href={href}
              onClick={() => recordOutcome("overview_understood")}
              className="flex min-h-12 items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-950 hover:bg-amber-100/70"
            >
              <Icon className="size-4 shrink-0 text-amber-800" aria-hidden="true" />
              <span className="flex-1">{text}</span>
              <ChevronRight className="size-4 shrink-0 text-amber-800" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
      {period && <p className="sr-only">These exceptions apply to all your records, not only this month.</p>}
    </section>
  );
}

function Estimate({ summary, period }: { summary: MoneySummary; period: Period }) {
  const headline = coverageHeadline(summary.coverage);
  const window = formatRange(summary.coverage.window_start, summary.coverage.window_end);
  const linkSuffix = periodParams(period);
  const lines = [
    {
      label: "Tracked income",
      value: summary.tracked_income_minor,
      sign: "+",
      href: `/transactions?status=confirmed${linkSuffix}`,
      note: `${plural(summary.income_transaction_count, "confirmed record", "confirmed records")}`,
    },
    {
      label: "Confirmed net outflows",
      value: summary.confirmed_outflows_minor,
      sign: "−",
      href: `/transactions?status=confirmed${linkSuffix}`,
      note: "Refunds reduce spending; transfers between your accounts aren't counted",
    },
    {
      label: "Unresolved obligations",
      value: summary.unresolved_commitments_minor,
      sign: "−",
      href: "#obligations",
      note: [
        summary.overdue_commitments_minor ? `${formatMoney(summary.overdue_commitments_minor)} overdue` : null,
        summary.uncertain_commitments_minor ? `${formatMoney(summary.uncertain_commitments_minor)} unverified` : null,
      ]
        .filter(Boolean)
        .join(" · ") || "Due by the end of the period, until paid or dismissed",
    },
  ];
  return (
    <section aria-labelledby="estimate-title" className="relative overflow-hidden rounded-[2rem] bg-ink p-5 text-white sm:p-8">
      <div aria-hidden="true" className="pointer-events-none absolute -top-24 -right-24 size-72 rounded-full bg-[radial-gradient(circle,rgba(155,92,255,0.45),transparent_65%)]" />
      <div className="relative grid gap-6 lg:grid-cols-[1fr_1.1fr] lg:gap-10">
        <div>
          <h2 id="estimate-title" className="text-sm font-medium text-white/80">
            Estimated unallocated · {period ? monthLabel(period.year, period.month) : "this month"}
          </h2>
          <p className="mt-3 text-4xl font-semibold tracking-tight tabular-nums sm:text-5xl">
            {formatMoney(summary.estimated_unallocated_minor)}
          </p>
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-white/80">{recordsNote}</p>
          <dl className="mt-5 space-y-1.5 text-sm">
            <div className="flex flex-wrap gap-x-2">
              <dt className="text-white/70">Last successful scan</dt>
              <dd className="font-medium">
                {summary.coverage.last_successful_scan_at ? formatDayTime(summary.coverage.last_successful_scan_at) : "none yet"}
              </dd>
            </div>
            <div className="flex flex-wrap gap-x-2">
              <dt className="text-white/70">Emails checked</dt>
              <dd className="font-medium">{window ?? "unknown"} · {headline.label.toLowerCase()}</dd>
            </div>
          </dl>
          <div className="mt-6 flex flex-wrap gap-2">
            <Button asChild className="bg-white text-ink hover:bg-lilac">
              <Link href="/assistant">
                <Sparkles aria-hidden="true" /> Ask about my money
              </Link>
            </Button>
            <Button asChild variant="ghost" className="text-white hover:bg-white/10 hover:text-white">
              <Link href="/sources">
                Sources <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </div>
        <div className="rounded-3xl bg-white/[0.07] p-4 ring-1 ring-white/15 sm:p-5">
          <h3 className="text-sm font-semibold">How this is calculated</h3>
          <ul className="mt-3 divide-y divide-white/10">
            {lines.map((line) => (
              <li key={line.label}>
                <Link
                  href={line.href}
                  onClick={() => recordOutcome("overview_understood")}
                  className="flex items-start justify-between gap-3 rounded-xl py-3 hover:bg-white/5"
                >
                  <span>
                    <span className="block text-sm font-medium">{line.label}</span>
                    <span className="block text-xs text-white/70">{line.note}</span>
                  </span>
                  <span className="shrink-0 text-sm font-semibold tabular-nums">
                    {line.sign} {formatMoney(line.value)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-2 flex justify-between gap-3 border-t border-white/20 pt-3 text-sm font-semibold">
            <span>Estimated unallocated</span>
            <span className="tabular-nums">{formatMoney(summary.estimated_unallocated_minor)}</span>
          </p>
          {summary.pending_review_count > 0 && (
            <Link href="/review" className="mt-3 block rounded-2xl bg-white/10 p-3 text-xs leading-relaxed hover:bg-white/15">
              <span className="font-semibold">Not included:</span>{" "}
              {plural(summary.pending_review_count, "record", "records")} ({formatMoney(summary.pending_review_minor)}) from this period
              {summary.pending_review_count === 1 ? " waits" : " wait"} for review. Review them →
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

function Categories({ summary, period }: { summary: MoneySummary; period: Period }) {
  const rows = summary.categories.filter((item) => item.amount_minor !== 0);
  const largest = Math.max(1, ...rows.map((row) => Math.abs(row.amount_minor)));
  return (
    <section aria-labelledby="categories-title" className="surface rounded-3xl p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="categories-title" className="text-lg font-semibold">Where it went</h2>
        <p className="text-xs text-ink-soft">Largest first</p>
      </div>
      {!rows.length ? (
        <p className="mt-4 text-sm text-ink-soft">No confirmed spending in this period yet.</p>
      ) : (
        <ul className="mt-4 space-y-1">
          {rows.map((item) => {
            const refund = item.amount_minor < 0;
            return (
              <li key={item.category}>
                <Link
                  href={`/transactions?category=${item.category}&status=confirmed${periodParams(period)}`}
                  onClick={() => recordOutcome("overview_understood")}
                  className="block rounded-2xl px-2 py-2.5 hover:bg-canvas"
                >
                  <span className="flex justify-between gap-4 text-sm">
                    <span>
                      {categoryLabels[item.category]}
                      <span className="text-xs text-ink-soft"> · {plural(item.transaction_count, "record", "records")}</span>
                    </span>
                    <strong className={cn("tabular-nums", refund && "text-positive")}>
                      {refund ? `Net refund ${formatMoney(-item.amount_minor)}` : formatMoney(item.amount_minor)}
                    </strong>
                  </span>
                  <span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                    <span
                      className={cn("block h-full rounded-full", refund ? "bg-positive" : "bg-violet")}
                      style={{ width: `${Math.max(2, (Math.abs(item.amount_minor) / largest) * 100)}%` }}
                    />
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      <p className="mt-3 text-xs leading-relaxed text-ink-soft">
        Refunds count against the original purchase&apos;s category. Transfers between your own accounts aren&apos;t spending.
      </p>
    </section>
  );
}

function Obligations({ onOpen, version }: { onOpen: (id: string) => void; version: number }) {
  const [showAll, setShowAll] = useState(false);
  const status = showAll ? "all" : "unresolved";
  const obligations = useResource(`obligations:${status}:${version}`, (signal) => getObligations(status, signal));
  const items = obligations.stale ? null : obligations.data?.items;
  return (
    <section id="obligations" aria-labelledby="obligations-title" className="surface scroll-mt-24 rounded-3xl p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="obligations-title" className="text-lg font-semibold">Bills and obligations</h2>
        <Button variant="ghost" size="sm" onClick={() => setShowAll((value) => !value)} aria-pressed={showAll}>
          {showAll ? "Show unresolved only" : "Include paid and dismissed"}
        </Button>
      </div>
      <p className="mt-1 text-xs text-ink-soft">Unresolved ones are deducted from your estimate — open one to check or resolve it.</p>
      {obligations.status === "loading" && <LoadingPanel className="mt-3 shadow-none" label="Loading obligations…" />}
      <RefreshingLabel active={obligations.status === "refreshing"}>Updating…</RefreshingLabel>
      {obligations.error !== null && (
        <ProblemNotice className="mt-3" problem={describeProblem(obligations.error, "Obligations couldn't be loaded")} onRetry={obligations.reload} />
      )}
      {items && !items.length && <p className="mt-4 text-sm text-ink-soft">No {showAll ? "" : "unresolved "}obligations in your records.</p>}
      {items && items.length > 0 && (
        <ul className="mt-3 divide-y">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                data-obligation-id={item.id}
                onClick={() => onOpen(item.id)}
                className="flex w-full items-center justify-between gap-4 py-3 text-left hover:bg-canvas"
              >
                <span className="min-w-0">
                  <span className="block text-sm font-medium break-words">{item.label}</span>
                  <span className="mt-0.5 block text-xs text-ink-soft">
                    {obligationKindLabels[item.kind]} · {item.liability_state === "overdue" ? "was due" : "due"} {formatDay(item.due_date)}
                    {item.uncertain && " · unverified"}
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <strong className="block text-sm tabular-nums">{formatMoney(item.amount_minor)}</strong>
                  <span
                    className={cn(
                      "mt-0.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      item.liability_state === "overdue" ? "bg-amber-50 text-amber-900" : "bg-muted text-ink-soft",
                    )}
                  >
                    {liabilityLabels[item.liability_state]}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function OverviewScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const period = readPeriod(new URLSearchParams(params.toString()));
  const summary = useResource(`summary:${period ? `${period.year}-${period.month}` : "current"}`, (signal) => getSummary(period, signal));
  const [obligation, setObligation] = useState<string | null>(null);
  const [changes, setChanges] = useState(0);
  const data = summary.stale ? null : summary.data;
  const [year = 2026, month = 1] = istDate(new Date()).split("-").map(Number);
  const months = Array.from({ length: 18 }, (_, index) => {
    const offset = month - 1 - index;
    return { year: year + Math.floor(offset / 12), month: (((offset % 12) + 12) % 12) + 1 };
  });
  const empty = data && !data.income_transaction_count && !data.outflow_transaction_count && !data.commitment_count;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Overview"
        description={
          data
            ? `Your household · ${formatRange(data.period_start, data.period_end)} · as of ${formatDay(data.as_of)}`
            : "Your household's tracked money"
        }
        actions={
          <>
            <label className="sr-only" htmlFor="overview-period">Period</label>
            <select
              id="overview-period"
              value={period ? `${period.year}-${period.month}` : ""}
              onChange={(event) => {
                const [y, m] = event.target.value.split("-");
                update({ year: y || null, month: m || null });
              }}
              className="h-11 rounded-full border border-input bg-white px-4 text-sm font-semibold"
            >
              <option value="">This month</option>
              {months.slice(1).map((item) => (
                <option key={`${item.year}-${item.month}`} value={`${item.year}-${item.month}`}>
                  {monthLabel(item.year, item.month)}
                </option>
              ))}
            </select>
            <Button variant="outline" onClick={summary.reload} disabled={summary.status === "loading" || summary.status === "refreshing"}>
              <RefreshCw aria-hidden="true" /> Refresh
            </Button>
          </>
        }
      />
      <RefreshingLabel active={summary.status === "refreshing"}>Refreshing your overview…</RefreshingLabel>
      {summary.status === "loading" && <LoadingPanel label="Loading your overview…" />}
      {summary.error !== null && (
        <ProblemNotice
          problem={describeProblem(summary.error, data ? "Couldn't refresh — showing the last loaded overview" : "Your overview couldn't be loaded")}
          onRetry={summary.reload}
        />
      )}
      {empty && period && (
        <EmptyState icon={Inbox} title={`No records for ${monthLabel(period.year, period.month)}`}>
          Nothing was imported for this month. Choose another period, or add a source that covers it.
        </EmptyState>
      )}
      {empty && !period && (
        <EmptyState
          icon={Inbox}
          title="No household records yet"
          actions={
            <>
              <Button asChild>
                <Link href="/sources">Add a source</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link href="/demo">Explore sample data</Link>
              </Button>
            </>
          }
        >
          Connect Gmail or upload emails to build your tracked records. The sample is read-only and never changes your records.
        </EmptyState>
      )}
      {data && (
        <>
          <Estimate summary={data} period={period} />
          <Exceptions summary={data} period={period} />
          <div className="grid items-start gap-5 xl:grid-cols-2">
            <Categories summary={data} period={period} />
            <Obligations onOpen={setObligation} version={changes} />
          </div>
        </>
      )}
      <SimulationPanel current={summary.data && !summary.stale && !period ? summary.data : null} />
      <ObligationDialog
        id={obligation}
        onClose={() => setObligation(null)}
        onChanged={() => {
          setChanges((value) => value + 1);
          summary.reload();
        }}
      />
    </div>
  );
}
