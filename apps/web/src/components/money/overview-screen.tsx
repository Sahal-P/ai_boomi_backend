"use client";

import {
  CalendarClock,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Inbox,
  ListChecks,
  MessageCircle,
  Plus,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { EmptyState, LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { EmptyMonthArt, NoRecordsArt } from "@/components/illustrations/scenes";
import { BudgetsCard } from "@/components/money/budgets-card";
import { MonthSelect } from "@/components/money/month-select";
import { ObligationDialog } from "@/components/money/obligation-dialog";
import { useQuickAdd } from "@/components/money/quick-add-provider";
import { AnimatedAmount } from "@/components/motion/animated-amount";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useRecordsChanged } from "@/hooks/use-records-changed";
import { useResource } from "@/hooks/use-resource";
import { chatLink } from "@/lib/api/auth";
import {
  formatMoney,
  getObligations,
  getSummary,
  periodFromParams,
  periodSearch,
  type MoneySummary,
  type Period,
} from "@/lib/api/money";
import { recordOutcome } from "@/lib/api/privacy";
import { formatDay, formatPeriod, monthLabel } from "@/lib/dates";
import { liabilityLabels, obligationKindLabels } from "@/lib/labels";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** The month's one number, with the three figures behind it and the full working on request. */
function Hero({ summary, period }: { summary: MoneySummary; period: Period }) {
  const suffix = periodSearch(period);
  const stats = [
    { label: "Money in", value: summary.tracked_income_minor, sign: "+", href: `/transactions?status=confirmed${suffix}` },
    { label: "Money out", value: summary.confirmed_outflows_minor, sign: "−", href: `/transactions?status=confirmed${suffix}` },
    { label: "Bills due", value: summary.unresolved_commitments_minor, sign: "−", href: "#obligations" },
  ];
  const lines = [
    {
      label: "Money in",
      value: summary.tracked_income_minor,
      sign: "+",
      href: `/transactions?status=confirmed${suffix}`,
      note: plural(summary.income_transaction_count, "confirmed record", "confirmed records"),
    },
    {
      label: "Money out",
      value: summary.confirmed_outflows_minor,
      sign: "−",
      href: `/transactions?status=confirmed${suffix}`,
      note: "Refunds reduce spending; transfers between your accounts aren't counted",
    },
    {
      label: "Bills due",
      value: summary.unresolved_commitments_minor,
      sign: "−",
      href: "#obligations",
      note:
        [
          summary.overdue_commitments_minor ? `${formatMoney(summary.overdue_commitments_minor)} overdue` : null,
          summary.uncertain_commitments_minor ? `${formatMoney(summary.uncertain_commitments_minor)} unverified` : null,
        ]
          .filter(Boolean)
          .join(" · ") || "Due by the end of the month, until paid or dismissed",
    },
  ];
  return (
    <section aria-labelledby="estimate-title" className="solid-hero relative overflow-hidden rounded-3xl p-5 sm:p-8">
      {/* Halftone corner: the illustrations' dot language, kept to the hero's empty corner. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-16 -right-16 size-64 bg-[radial-gradient(rgb(14_16_19/0.16)_1px,transparent_1.5px)] [background-size:9px_9px] [mask-image:radial-gradient(circle,#000_20%,transparent_68%)]"
      />
      <div className="relative">
        <h2 id="estimate-title" className="text-sm font-medium text-sunflower-ink">
          Left {period ? `in ${monthLabel(period.year, period.month)}` : "this month"}
        </h2>
        <p className="mt-2 text-[2.75rem] leading-none font-semibold tracking-[-0.04em] sm:text-6xl">
          <AnimatedAmount amountMinor={summary.estimated_unallocated_minor} format={formatMoney} duration={1.2} />
        </p>
        <p className="mt-3 text-sm text-sunflower-ink">From your confirmed records — not your bank balance.</p>

        {/* A white tint on yellow, never glass: blurred yellow over the blue field turns muddy. */}
        <ul className="mt-5 grid gap-2 min-[400px]:grid-cols-3 sm:max-w-2xl">
          {stats.map((stat) => (
            <li key={stat.label}>
              <Link
                href={stat.href}
                onClick={() => recordOutcome("overview_explanation_opened")}
                className="flex items-baseline justify-between gap-3 rounded-2xl bg-white/55 px-4 py-3 transition-colors hover:bg-white/75 min-[400px]:block"
              >
                <span className="block text-xs font-medium text-sunflower-ink">{stat.label}</span>
                <span className="block text-base font-semibold tabular-nums min-[400px]:mt-1">
                  {stat.sign} {formatMoney(stat.value)}
                </span>
              </Link>
            </li>
          ))}
        </ul>

        <details className="group mt-3 rounded-2xl bg-white/55 sm:max-w-2xl">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-4 py-2.5 text-sm font-semibold [&::-webkit-details-marker]:hidden">
            How is this worked out?
            <ChevronDown className="size-4 shrink-0 transition-transform duration-300 group-open:rotate-180" aria-hidden="true" />
          </summary>
          <div className="px-4 pb-4">
            <ul className="divide-y divide-ink/10">
              {lines.map((line) => (
                <li key={line.label}>
                  <Link
                    href={line.href}
                    onClick={() => recordOutcome("overview_explanation_opened")}
                    className="-mx-2 flex items-start justify-between gap-3 rounded-xl px-2 py-3 hover:bg-white/60"
                  >
                    <span>
                      <span className="block text-sm font-medium">{line.label}</span>
                      <span className="block text-xs text-ink-soft">{line.note}</span>
                    </span>
                    <span className="shrink-0 text-sm font-semibold tabular-nums">
                      {line.sign} {formatMoney(line.value)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-1 flex justify-between gap-3 border-t border-ink/15 pt-3 text-sm font-semibold">
              <span>Left</span>
              <span className="tabular-nums">{formatMoney(summary.estimated_unallocated_minor)}</span>
            </p>
            {summary.pending_review_count > 0 && (
              <Link href="/review" className="mt-3 block rounded-xl bg-ink p-3 text-xs leading-relaxed text-white hover:bg-ink/90">
                <span className="font-semibold">Not included:</span>{" "}
                {plural(summary.pending_review_count, "record", "records")} ({formatMoney(summary.pending_review_minor)}) from this period
                {summary.pending_review_count === 1 ? " waits" : " wait"} for review. Review them →
              </Link>
            )}
          </div>
        </details>
      </div>
    </section>
  );
}

/** One row of chips, only when something needs a look; each opens the place to fix it. */
function Attention({ summary }: { summary: MoneySummary }) {
  const { coverage } = summary;
  const items: { key: string; href: string; icon: typeof Inbox; text: string }[] = [];
  if (coverage.pending_review_count > 0) {
    items.push({ key: "review", href: "/review", icon: ListChecks, text: `${plural(coverage.pending_review_count, "record", "records")} to review` });
  }
  if (summary.overdue_commitment_count > 0) {
    items.push({
      key: "overdue",
      href: "#obligations",
      icon: CalendarClock,
      text: `${plural(summary.overdue_commitment_count, "bill", "bills")} overdue · ${formatMoney(summary.overdue_commitments_minor)}`,
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
  if (coverage.truncated) {
    items.push({ key: "limit", href: "/sources", icon: Inbox, text: "The last email check stopped at its limit" });
  }
  if (coverage.quarantined_count > 0) {
    items.push({
      key: "hold",
      href: "/transactions?dataset=quarantined&scope=all",
      icon: ShieldAlert,
      text: `${plural(coverage.quarantined_count, "record", "records")} on hold`,
    });
  }
  if (!items.length) return null;
  return (
    <section aria-label="Needs your attention">
      <ul className="flex flex-wrap gap-2">
        {items.map(({ key, href, icon: Icon, text }) => (
          <li key={key}>
            <Link
              href={href}
              onClick={() => recordOutcome("overview_explanation_opened")}
              className="inline-flex min-h-11 items-center gap-2 rounded-full border border-amber-200 bg-amber-50 py-2 pr-3 pl-4 text-sm font-medium text-amber-950 transition-colors hover:bg-amber-100/70"
            >
              <Icon className="size-4 shrink-0 text-amber-800" aria-hidden="true" />
              {text}
              <ChevronRight className="size-4 shrink-0 text-amber-800" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

const BILLS_SHOWN = 4;

function Bills({ onOpen, version }: { onOpen: (id: string) => void; version: number }) {
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const status = showAll ? "all" : "unresolved";
  const obligations = useResource(`obligations:${status}:${version}`, (signal) => getObligations(status, signal));
  const items = obligations.stale ? null : obligations.data?.items;
  const shown = items && !expanded ? items.slice(0, BILLS_SHOWN) : items;
  return (
    <section id="obligations" aria-labelledby="obligations-title" className="surface scroll-mt-24 rounded-3xl p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="obligations-title" className="text-lg font-semibold">Bills due</h2>
        <Button variant="ghost" size="sm" onClick={() => setShowAll((value) => !value)} aria-pressed={showAll}>
          {showAll ? "Show unresolved only" : "Include paid and dismissed"}
        </Button>
      </div>
      {obligations.status === "loading" && <LoadingPanel className="mt-3 shadow-none" label="Loading bills…" />}
      <RefreshingLabel active={obligations.status === "refreshing"}>Updating…</RefreshingLabel>
      {obligations.error !== null && (
        <ProblemNotice className="mt-3" problem={describeProblem(obligations.error, "Bills couldn't be loaded")} onRetry={obligations.reload} />
      )}
      {items && !items.length && (
        <p className="mt-3 text-sm text-ink-soft">{showAll ? "No bills in your records." : "Nothing due. Unpaid bills are taken off what's left."}</p>
      )}
      {shown && shown.length > 0 && (
        <ul className="mt-2 divide-y">
          {shown.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                data-obligation-id={item.id}
                onClick={() => onOpen(item.id)}
                className="-mx-2 flex w-[calc(100%+1rem)] items-center justify-between gap-4 rounded-xl px-2 py-3 text-left transition-colors hover:bg-white/50"
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
      {items && items.length > BILLS_SHOWN && (
        <Button variant="ghost" size="sm" className="mt-2" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
          {expanded ? "Show fewer" : `Show all ${items.length}`}
        </Button>
      )}
    </section>
  );
}

export function OverviewScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const period = periodFromParams(new URLSearchParams(params.toString()));
  const summary = useResource(`summary:${period ? `${period.year}-${period.month}` : "current"}`, (signal) => getSummary(period, signal));
  const [obligation, setObligation] = useState<string | null>(null);
  const [changes, setChanges] = useState(0);
  const quickAdd = useQuickAdd();
  const { signIn } = useHouseholdAccess();
  useRecordsChanged(() => {
    setChanges((value) => value + 1);
    summary.reload();
  });
  const data = summary.stale ? null : summary.data;
  const empty = data && !data.income_transaction_count && !data.outflow_transaction_count && !data.commitment_count;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Home"
        description={
          data ? `${formatPeriod(data.period_start, data.period_end)} · as of ${formatDay(data.as_of)}` : "Your household's money"
        }
        actions={
          // One row even at 320 px: the month takes the room and Refresh is an icon.
          <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
            <MonthSelect
              id="home-period"
              period={period}
              onChange={(next) => update(next ? { year: String(next.year), month: String(next.month) } : { year: null, month: null })}
              className="flex-1 sm:flex-none"
            />
            <Button
              variant="outline"
              size="icon"
              aria-label="Refresh"
              className="shrink-0"
              onClick={summary.reload}
              disabled={summary.status === "loading" || summary.status === "refreshing"}
            >
              <RefreshCw aria-hidden="true" />
            </Button>
          </div>
        }
      />
      <RefreshingLabel active={summary.status === "refreshing"}>Refreshing…</RefreshingLabel>
      {summary.status === "loading" && <LoadingPanel label="Loading your month…" />}
      {summary.error !== null && (
        <ProblemNotice
          problem={describeProblem(summary.error, data ? "Couldn't refresh — showing what was last loaded" : "Home couldn't be loaded")}
          onRetry={summary.reload}
        />
      )}
      {empty && period && (
        <EmptyState illustration={<EmptyMonthArt />} title={`No records for ${monthLabel(period.year, period.month)}`}>
          Nothing was added for this month. Choose another month, or add an entry with +.
        </EmptyState>
      )}
      {empty && !period && (
        <EmptyState
          illustration={<NoRecordsArt />}
          title="Add what you spent today"
          actions={
            <>
              <Button onClick={quickAdd.open}>
                <Plus aria-hidden="true" /> Add an entry
              </Button>
              {signIn?.whatsapp_number && (
                <Button asChild variant="outline">
                  <a href={chatLink(signIn.whatsapp_number)} target="_blank" rel="noopener noreferrer">
                    <MessageCircle aria-hidden="true" /> Send it on WhatsApp
                  </a>
                </Button>
              )}
              {signIn?.gmail !== false && (
                <Button asChild variant="outline">
                  <Link href="/sources">Add a source</Link>
                </Button>
              )}
              <Button asChild variant="ghost">
                <Link href="/demo">Explore sample data</Link>
              </Button>
            </>
          }
        >
          Say or type it, like &ldquo;Paid the milkman 500&rdquo;, or send it on WhatsApp — a voice
          note, &ldquo;chai 20, auto 50&rdquo; or a photo of the bill. FinBoy keeps the amount, date
          and category. The sample is read-only and never changes your records.
        </EmptyState>
      )}
      {data && !empty && (
        <>
          <Hero summary={data} period={period} />
          <Attention summary={data} />
          <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
            <Bills onOpen={setObligation} version={changes} />
            <BudgetsCard period={period} version={changes} compact />
          </div>
        </>
      )}
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
