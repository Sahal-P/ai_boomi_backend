"use client";

import { ArrowDownRight, ArrowUpRight, ChartColumn, Plus, Table2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ColumnChart, type ColumnGroup, type ColumnSeries } from "@/components/charts/column-chart";
import { DonutChart } from "@/components/charts/donut-chart";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { EmptyState, LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { EmptyMonthArt } from "@/components/illustrations/scenes";
import { BudgetsCard } from "@/components/money/budgets-card";
import { MonthSelect } from "@/components/money/month-select";
import { useQuickAdd } from "@/components/money/quick-add-provider";
import { AnimatedAmount } from "@/components/motion/animated-amount";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useRecordsChanged } from "@/hooks/use-records-changed";
import { useResource, type Resource } from "@/hooks/use-resource";
import {
  formatMoney,
  getSummary,
  periodFromParams,
  periodSearch,
  type MoneySummary,
  type Period,
} from "@/lib/api/money";
import { daysCounted, foldSlices, sharePercent, type Slice } from "@/lib/charts";
import { monthLabel, monthsBack, recentMonths, type Month } from "@/lib/dates";
import { categoryLabels } from "@/lib/labels";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

// Spending's amber ramp, darkest for the largest slice; the folded tail is grey.
const RAMP = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const SERIES: ColumnSeries[] = [
  { key: "in", label: "Money in", swatch: "bg-chart-in" },
  { key: "out", label: "Money out", swatch: "bg-chart-out" },
];
const shortMonth = new Intl.DateTimeFormat("en-IN", { month: "short", timeZone: "UTC" });
const monthName = (month: Month) => shortMonth.format(new Date(Date.UTC(month.year, month.month - 1, 1)));
const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

function sliceLabel(key: Slice["key"]) {
  return key === "rest" ? "Everything else" : categoryLabels[key];
}

/** Three figures for the month: spent (against the month before), money in, and a daily average. */
function Figures({ summary, before, beforeMonth }: { summary: MoneySummary; before: MoneySummary | undefined; beforeMonth: Month | undefined }) {
  const spent = summary.confirmed_outflows_minor;
  const days = daysCounted(summary.period_start, summary.period_end, summary.as_of);
  const previous = before?.confirmed_outflows_minor;
  const change = previous && previous > 0 ? (spent - previous) / previous : null;
  const versus = beforeMonth ? monthLabel(beforeMonth.year, beforeMonth.month).split(" ")[0] : null;
  const tiles = [
    {
      label: "Spent",
      amount: spent,
      note:
        change === null || !versus ? (
          "Confirmed spending"
        ) : Math.round(change * 100) === 0 ? (
          `About the same as ${versus}`
        ) : (
          <span className="inline-flex items-center gap-1">
            {change > 0 ? <ArrowUpRight className="size-3.5" aria-hidden="true" /> : <ArrowDownRight className="size-3.5" aria-hidden="true" />}
            {Math.abs(Math.round(change * 100))}% {change > 0 ? "more" : "less"} than {versus}
          </span>
        ),
    },
    { label: "Money in", amount: summary.tracked_income_minor, note: plural(summary.income_transaction_count, "entry", "entries") },
    { label: "Daily average", amount: Math.round(spent / days / 100) * 100, note: `Spending over ${plural(days, "day", "days")}` },
  ];
  return (
    <ul className="grid gap-3 sm:grid-cols-3">
      {tiles.map((tile) => (
        <li key={tile.label} className="surface rounded-3xl p-5">
          <p className="text-sm font-medium text-ink-soft">{tile.label}</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-[-0.02em]">
            <AnimatedAmount amountMinor={tile.amount} format={formatMoney} duration={1} />
          </p>
          <p className="mt-1 text-xs text-ink-soft">{tile.note}</p>
        </li>
      ))}
    </ul>
  );
}

/** The donut and its legend table: every category with its amount and share, each a link. */
function Categories({ summary, period }: { summary: MoneySummary; period: Period }) {
  const [active, setActive] = useState<string | null>(null);
  const { slices, spending, refunds, total_minor } = foldSlices(summary.categories);
  // Few slices spread across the whole ramp, so neighbours never sit one step apart.
  const named = slices.filter((slice) => slice.key !== "rest").length;
  const step = (index: number) => (named > 1 ? Math.round((index * (RAMP.length - 1)) / (named - 1)) : 2);
  const colour = new Map<string, string>(
    slices.map((slice, index) => [slice.key, slice.key === "rest" ? "var(--chart-rest)" : (RAMP[step(index)] ?? "var(--chart-rest)")]),
  );
  const drawn = new Set<string>(slices.map((slice) => slice.key));
  const sliceOf = (category: string) => (drawn.has(category) ? category : "rest");
  const readout = slices.find((slice) => slice.key === active);
  const link = (category: string) => `/transactions?category=${category}&status=confirmed${periodSearch(period)}`;
  return (
    <section aria-labelledby="where-title" className="surface rounded-3xl p-5 sm:p-6">
      <h2 id="where-title" className="text-lg font-semibold">Where your money went</h2>
      <p className="mt-1 text-xs text-ink-soft">Confirmed spending by category. Tap a slice or a row.</p>
      {!slices.length ? (
        <p className="mt-4 text-sm text-ink-soft">No confirmed spending in this month yet.</p>
      ) : (
        <div className="mt-5 grid items-center gap-6 sm:grid-cols-[minmax(0,13rem)_1fr]">
          <DonutChart
            slices={slices.map((slice) => ({ key: slice.key, share: slice.share, color: colour.get(slice.key) ?? "var(--chart-rest)" }))}
            active={active}
            onActive={setActive}
          >
            <span className="block text-xs font-medium text-ink-soft">{readout ? sliceLabel(readout.key) : "Spent"}</span>
            <span className="mt-1 block text-lg font-semibold tracking-[-0.02em] tabular-nums sm:text-xl">
              {formatMoney(readout ? readout.amount_minor : total_minor)}
            </span>
            <span className="block text-xs text-ink-soft">{readout ? sharePercent(readout.share) : "this month"}</span>
          </DonutChart>
          <table className="w-full text-sm">
            <caption className="sr-only">Confirmed spending by category</caption>
            {/* Headers for screen readers; the row stays in the table so the columns keep them. */}
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">Category</span></th>
                <th scope="col"><span className="sr-only">Amount</span></th>
                <th scope="col"><span className="sr-only">Share</span></th>
              </tr>
            </thead>
            <tbody>
              {spending.map((row) => {
                const key = sliceOf(row.category);
                return (
                  <tr
                    key={row.category}
                    className={cn("transition-opacity duration-300", active !== null && active !== key && "opacity-45")}
                    onPointerEnter={() => setActive(key)}
                    onPointerLeave={() => setActive(null)}
                  >
                    <td className="py-1 pr-2">
                      <Link
                        href={link(row.category)}
                        onFocus={() => setActive(key)}
                        onBlur={() => setActive(null)}
                        className="flex min-h-9 items-center gap-2.5 rounded-lg font-medium underline-offset-4 hover:underline"
                      >
                        <span className="size-2.5 shrink-0 rounded-full" style={{ background: colour.get(key) }} aria-hidden="true" />
                        {categoryLabels[row.category]}
                      </Link>
                    </td>
                    <td className="py-1 text-right font-semibold tabular-nums">{formatMoney(row.amount_minor)}</td>
                    <td className="w-12 py-1 pl-2 text-right text-ink-soft tabular-nums">
                      {sharePercent(row.amount_minor / total_minor)}
                    </td>
                  </tr>
                );
              })}
              {refunds.map((row) => (
                <tr key={row.category}>
                  <td className="py-1 pr-2">
                    <Link href={link(row.category)} className="flex min-h-9 items-center gap-2.5 rounded-lg font-medium underline-offset-4 hover:underline">
                      <span className="size-2.5 shrink-0 rounded-full border border-positive" aria-hidden="true" />
                      {categoryLabels[row.category]}
                    </Link>
                  </td>
                  <td colSpan={2} className="py-1 text-right font-semibold text-positive tabular-nums">
                    Net refund {formatMoney(-row.amount_minor)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-4 text-xs leading-relaxed text-ink-soft">
        Refunds count against the original purchase&apos;s category. Transfers between your own accounts aren&apos;t spending.
      </p>
    </section>
  );
}

/** Money in and out for the six months ending with the chosen one, as columns or a table. */
function Trend({
  months,
  trend,
  chosen,
}: {
  months: Month[];
  trend: Resource<MoneySummary[]>;
  chosen: string;
}) {
  const [table, setTable] = useState(false);
  const results = trend.stale ? null : trend.data;
  const groups: ColumnGroup[] = results
    ? months.map((month, index) => ({
        key: `${month.year}-${month.month}`,
        label: monthName(month),
        title: monthLabel(month.year, month.month),
        values: [results[index]?.tracked_income_minor ?? 0, results[index]?.confirmed_outflows_minor ?? 0],
        emphasis: `${month.year}-${month.month}` === chosen,
      }))
    : [];
  return (
    <section aria-labelledby="trend-title" className="surface rounded-3xl p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="trend-title" className="text-lg font-semibold">Month by month</h2>
        <Button variant="ghost" size="sm" aria-pressed={table} onClick={() => setTable((value) => !value)}>
          {table ? <ChartColumn aria-hidden="true" /> : <Table2 aria-hidden="true" />}
          {table ? "Show chart" : "Show as table"}
        </Button>
      </div>
      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-soft">
        {SERIES.map((item) => (
          <li key={item.key} className="flex items-center gap-1.5">
            <span className={cn("size-2.5 rounded-full", item.swatch)} aria-hidden="true" />
            {item.label}
          </li>
        ))}
      </ul>
      {trend.status === "loading" && <LoadingPanel className="mt-4 shadow-none" label="Loading six months…" />}
      {trend.error !== null && (
        <ProblemNotice className="mt-4" problem={describeProblem(trend.error, "The last six months couldn't be loaded")} onRetry={trend.reload} />
      )}
      {groups.length > 0 && (
        <>
          {!table && (
            <div className="mt-10">
              <ColumnChart series={SERIES} groups={groups} />
            </div>
          )}
          {/* Hidden from sight by a wrapper: a table sizes to its content, so it can't shrink itself. */}
          <div className={cn("mt-4", !table && "sr-only")}>
            <table className="w-full text-sm">
              <caption className="sr-only">Money in and money out, the last six months</caption>
              <thead>
                <tr className="text-left text-xs text-ink-soft">
                  <th scope="col" className="py-2 font-medium">Month</th>
                  <th scope="col" className="py-2 text-right font-medium">Money in</th>
                  <th scope="col" className="py-2 text-right font-medium">Money out</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {groups.map((group) => (
                  <tr key={group.key} className={group.emphasis ? "font-semibold" : undefined}>
                    <th scope="row" className="py-2 text-left font-medium">{group.title}</th>
                    <td className="py-2 text-right tabular-nums">{formatMoney(group.values[0] ?? 0)}</td>
                    <td className="py-2 text-right tabular-nums">{formatMoney(group.values[1] ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

export function ReportsScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const quickAdd = useQuickAdd();
  const period = periodFromParams(new URLSearchParams(params.toString()));
  const [current = { year: 2026, month: 1 }] = recentMonths(1);
  const month = period ?? current;
  const chosen = `${month.year}-${month.month}`;
  const months = monthsBack(month.year, month.month, 6).reverse();
  const summary = useResource(`report:${chosen}`, (signal) => getSummary(period, signal));
  const trend = useResource(`trend:${chosen}`, (signal) => Promise.all(months.map((item) => getSummary(item, signal))));
  const [changes, setChanges] = useState(0);
  useRecordsChanged(() => {
    summary.reload();
    trend.reload();
    setChanges((value) => value + 1);
  });
  const data = summary.stale ? null : summary.data;
  const results = trend.stale ? null : trend.data;
  const empty = data && !data.outflow_transaction_count && !data.income_transaction_count;
  // Home's "All budgets" lands here; the card's place is known only once everything above it is in.
  const settled = Boolean(data && results);
  useEffect(() => {
    if (settled && window.location.hash === "#budgets") document.getElementById("budgets")?.scrollIntoView({ block: "start" });
  }, [settled]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reports"
        description="Where your money goes, month by month."
        actions={
          <MonthSelect
            id="reports-period"
            period={period}
            onChange={(next) => update(next ? { year: String(next.year), month: String(next.month) } : { year: null, month: null })}
            className="w-full sm:w-auto"
          />
        }
      />
      <RefreshingLabel active={summary.status === "refreshing"}>Refreshing…</RefreshingLabel>
      {summary.status === "loading" && <LoadingPanel label="Loading your reports…" />}
      {summary.error !== null && (
        <ProblemNotice
          problem={describeProblem(summary.error, data ? "Couldn't refresh — showing what was last loaded" : "Reports couldn't be loaded")}
          onRetry={summary.reload}
        />
      )}
      {empty && (
        <EmptyState
          illustration={<EmptyMonthArt />}
          title={`Nothing recorded for ${monthLabel(month.year, month.month)}`}
          actions={
            <Button onClick={quickAdd.open}>
              <Plus aria-hidden="true" /> Add an entry
            </Button>
          }
        >
          Reports fill in as you add what you spend and receive, here or on WhatsApp.
        </EmptyState>
      )}
      {data && !empty && (
        <>
          <Figures summary={data} before={results?.[results.length - 2]} beforeMonth={months[months.length - 2]} />
          <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-2">
            <Categories summary={data} period={period} />
            <Trend months={months} trend={trend} chosen={chosen} />
          </div>
          <BudgetsCard period={period} version={changes} />
        </>
      )}
    </div>
  );
}
