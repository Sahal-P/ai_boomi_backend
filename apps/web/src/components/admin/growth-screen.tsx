"use client";

import { ArrowDownRight, ArrowUpRight, ChartColumn, ChevronRight, Minus, Table2 } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type ReactNode, useState } from "react";
import { count, Panel, RefreshButton, StatTile } from "@/components/admin/admin-bits";
import { GrowthFunnel } from "@/components/admin/growth-funnel";
import { RetentionGrid } from "@/components/admin/retention-grid";
import { PageHeader } from "@/components/app-shell/page-header";
import { ColumnChart, type ColumnGroup } from "@/components/charts/column-chart";
import { LineChart, type LineSeries } from "@/components/charts/line-chart";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useResource } from "@/hooks/use-resource";
import { getGrowth, GROWTH_PERIODS, type Growth, type GrowthPeriod, type GrowthPoint } from "@/lib/api/admin";
import { countLabel, countTicks } from "@/lib/charts";
import {
  axisLabel,
  comparison,
  type Direction,
  type GrowthUnit,
  PERIOD_LABELS,
  PERIOD_UNITS,
  percentOf,
  pointTitle,
  showsLabel,
  signed,
} from "@/lib/growth";
import { describeProblem } from "@/lib/messages";
import { span } from "@/lib/signup-sources";
import { cn } from "@/lib/utils";

const isPeriod = (value: string | null): value is GrowthPeriod =>
  GROWTH_PERIODS.some((period) => period === value);
const UNIT_TITLES: Record<GrowthUnit, string> = { day: "Day", week: "Week", month: "Month" };
const scale = (max: number) => countTicks(max);

/** Three presets in one glass segmented control, above everything they scope. */
function PeriodPicker({ value, onChange }: { value: GrowthPeriod; onChange: (period: GrowthPeriod) => void }) {
  return (
    <div role="group" aria-label="Period" className="lg-static inline-flex max-w-full rounded-full p-1">
      {GROWTH_PERIODS.map((period) => {
        const on = period === value;
        return (
          <button
            key={period}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(period)}
            className={cn(
              "relative h-10 rounded-full px-3.5 text-sm font-semibold whitespace-nowrap transition-colors sm:px-4",
              on ? "text-ink" : "text-ink-soft hover:text-ink",
            )}
          >
            {on && (
              <motion.span
                layoutId="growth-period"
                className="lg-knob absolute inset-0 rounded-full"
                transition={{ type: "spring", stiffness: 420, damping: 30 }}
              />
            )}
            <span className="relative">{PERIOD_LABELS[period]}</span>
          </button>
        );
      })}
    </div>
  );
}

const TRENDS: Record<Direction, { Icon: typeof Minus; tone: string }> = {
  up: { Icon: ArrowUpRight, tone: "text-positive" },
  down: { Icon: ArrowDownRight, tone: "text-negative" },
  same: { Icon: Minus, tone: "text-ink-soft" },
};

/** A change against the period before: an arrow and the words, never colour alone. */
function Change({ direction, text }: { direction: Direction; text: string }) {
  const { Icon, tone } = TRENDS[direction];
  return (
    <span className={cn("inline-flex items-start gap-1 font-medium", tone)}>
      <Icon className="mt-px size-3.5 shrink-0" aria-hidden="true" />
      {text}
    </span>
  );
}

type Column = { title: string; value: (point: GrowthPoint) => number };

/** A chart's figures as a table: under the chart for screen readers, or in its place. */
function PointTable({ caption, unit, points, columns }: { caption: string; unit: GrowthUnit; points: GrowthPoint[]; columns: Column[] }) {
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="text-left text-xs text-ink-soft">
          <th scope="col" className="py-2 font-medium">
            {UNIT_TITLES[unit]}
          </th>
          {columns.map((column) => (
            <th key={column.title} scope="col" className="py-2 pl-3 text-right font-medium">
              {column.title}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-ink/[0.07]">
        {points.map((point) => (
          <tr key={point.start}>
            <th scope="row" className="py-2 text-left font-medium">
              {pointTitle(point, unit)}
            </th>
            {columns.map((column) => (
              <td key={column.title} className="py-2 pl-3 text-right tabular-nums">
                {count(column.value(point))}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** A panel with a chart and its table, and "Show as table" to swap them. */
function ChartPanel({
  title,
  description,
  legend,
  chart,
  table,
}: {
  title: string;
  description: string;
  legend?: ReactNode;
  chart: ReactNode;
  table: ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <Panel
      title={title}
      description={description}
      actions={
        <Button variant="ghost" size="sm" aria-pressed={asTable} onClick={() => setAsTable((value) => !value)}>
          {asTable ? <ChartColumn aria-hidden="true" /> : <Table2 aria-hidden="true" />}
          {asTable ? "Show chart" : "Show as table"}
        </Button>
      }
    >
      {legend}
      {!asTable && <div className="mt-12">{chart}</div>}
      {/* Hidden from sight by a wrapper: a table sizes to its content, so it can't shrink itself. */}
      <div className={cn("mt-4", !asTable && "sr-only")}>{table}</div>
    </Panel>
  );
}

function Legend({ items }: { items: { key: string; label: string; swatch: string; line?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-soft">
      {items.map((item) => (
        <li key={item.key} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={cn(item.line ? "h-0.5 w-4 rounded-full" : "size-2.5 rounded-[3px]", item.swatch)}
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function GrowthBody({ data }: { data: Growth }) {
  const { summary, points, unit, period } = data;
  const words = PERIOD_LABELS[period];
  const lines: LineSeries[] = [
    { key: "households", label: "All households", stroke: "var(--chart-in)", swatch: "bg-chart-in" },
    { key: "active", label: `Active that ${unit}`, stroke: "var(--chart-out)", swatch: "bg-chart-out" },
  ];
  const labelled = (point: GrowthPoint, index: number) =>
    showsLabel(index, points.length) ? axisLabel(point.start, unit) : "";
  const columns = (
    value: (point: GrowthPoint) => number,
    more: (point: GrowthPoint) => NonNullable<ColumnGroup["more"]>,
  ): ColumnGroup[] =>
    points.map((point, index) => ({
      key: point.start,
      label: labelled(point, index),
      title: pointTitle(point, unit),
      values: [value(point)],
      // The running day, week or month recedes: it is counted so far.
      emphasis: !point.partial,
      more: more(point),
    }));
  const first = summary.minutes_to_record === null ? "" : ` · median ${span(summary.minutes_to_record)} from sign-up`;
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="New households"
          value={count(summary.joined)}
          detail={<Change {...comparison(summary.joined, summary.joined_before, period)} />}
        />
        <StatTile
          label="Households now"
          value={count(summary.households)}
          detail={`${signed(summary.joined - summary.left)} in these ${words}: ${count(summary.joined)} joined, ${count(summary.left)} left`}
        />
        <StatTile
          label="Active in the last 7 days"
          value={count(summary.active_week)}
          detail={`of ${count(summary.households)} households · ${percentOf(summary.active_week, summary.households)}`}
        />
        <StatTile
          label="Made a first record"
          value={percentOf(summary.activated, summary.joined)}
          detail={
            summary.joined
              ? `${count(summary.activated)} of ${count(summary.joined)} new households${first}`
              : "No new households in this period."
          }
        />
      </div>

      {points.length === 0 ? (
        <Panel title="No self-serve households yet" description="Households appear here once they agree on WhatsApp or the web.">
          <p className="text-sm text-ink-soft">Page visits and sign-ups that haven&apos;t agreed show in the way in below.</p>
        </Panel>
      ) : (
        <>
          <ChartPanel
            title="Households"
            description={`All self-serve households at the end of each ${unit}, and how many were active in it: sent FinBoy a WhatsApp message or saved a record.`}
            legend={<Legend items={lines.map((line) => ({ ...line, line: true }))} />}
            chart={
              <LineChart
                series={lines}
                points={points.map((point, index) => ({
                  key: point.start,
                  label: labelled(point, index),
                  title: pointTitle(point, unit),
                  values: [point.households, point.active],
                }))}
              />
            }
            table={
              <PointTable
                caption={`Households and active households by ${unit}`}
                unit={unit}
                points={points}
                columns={[
                  { title: "All households", value: (point) => point.households },
                  { title: "Active", value: (point) => point.active },
                ]}
              />
            }
          />
          <div className="grid items-start gap-5 lg:grid-cols-2">
            <ChartPanel
              title="New households"
              description={`Households that agreed each ${unit}. The tooltip also shows those that left.`}
              chart={
                <ColumnChart
                  series={[{ key: "joined", label: "Joined", swatch: "bg-chart-in" }]}
                  groups={columns(
                    (point) => point.joined,
                    (point) => [{ label: "Left", value: count(point.left) }],
                  )}
                  format={count}
                  tick={countLabel}
                  scale={scale}
                  labelChosen={false}
                />
              }
              table={
                <PointTable
                  caption={`Households that joined and left by ${unit}`}
                  unit={unit}
                  points={points}
                  columns={[
                    { title: "Joined", value: (point) => point.joined },
                    { title: "Left", value: (point) => point.left },
                  ]}
                />
              }
            />
            <ChartPanel
              title="Records saved"
              description={`Records saved each ${unit}, confirmed or waiting for a check, and how many households saved them. Never their amounts.`}
              chart={
                <ColumnChart
                  series={[{ key: "records", label: "Records", swatch: "bg-chart-in" }]}
                  groups={columns(
                    (point) => point.records,
                    (point) => [{ label: "Households", value: count(point.recording) }],
                  )}
                  format={count}
                  tick={countLabel}
                  scale={scale}
                  labelChosen={false}
                />
              }
              table={
                <PointTable
                  caption={`Records saved by ${unit}`}
                  unit={unit}
                  points={points}
                  columns={[
                    { title: "Records", value: (point) => point.records },
                    { title: "Households", value: (point) => point.recording },
                  ]}
                />
              }
            />
          </div>
        </>
      )}

      <Panel
        title="From page to first record"
        description={`Visits to a FinBoy page in these ${words}, and how far each got, whenever it happened.`}
        actions={
          <Button asChild variant="ghost" size="sm">
            <Link href="/admin/signups">
              By source <ChevronRight aria-hidden="true" />
            </Link>
          </Button>
        }
      >
        <GrowthFunnel funnel={data.funnel} />
      </Panel>
      {points.length > 0 && (
        <Panel
          title="Coming back"
          description={`Of the households that agreed each ${data.cohort_unit}, the share active in each ${data.cohort_unit} after. ${UNIT_TITLES[data.cohort_unit]} 0 is the one they agreed in.`}
        >
          <RetentionGrid cohorts={data.cohorts} unit={data.cohort_unit} />
        </Panel>
      )}
    </>
  );
}

/** Growth over time for the people who run FinBoy (docs/admin-growth/contract.md). */
export function GrowthScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const asked = params.get("period");
  const period: GrowthPeriod = isPeriod(asked) ? asked : "30d";
  const growth = useResource(`admin-growth:${period}`, (signal) => getGrowth(period, signal));
  const busy = growth.stale || growth.status === "refreshing";
  return (
    <div className="space-y-5">
      <PageHeader
        title="Growth"
        description="How self-serve households join, stay and use FinBoy. Counts and dates only; the owner and the village pilot are left out."
        actions={<RefreshButton resource={growth} />}
      />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <PeriodPicker value={period} onChange={(next) => update({ period: next === "30d" ? null : next })} />
        <p className="text-xs text-ink-soft">By {PERIOD_UNITS[period]}, in India time. Weeks start on Monday.</p>
      </div>
      <RefreshingLabel active={busy}>Updating the charts…</RefreshingLabel>
      {growth.status === "loading" && <LoadingPanel label="Loading growth…" />}
      {growth.error !== null && (
        <ProblemNotice
          problem={describeProblem(growth.error, growth.data ? "Couldn't refresh — showing the last loaded charts" : "Growth couldn't be loaded")}
          onRetry={growth.reload}
        />
      )}
      {growth.data && (
        <div aria-busy={busy} className={cn("space-y-5 transition-opacity duration-300", busy && "opacity-60")}>
          <GrowthBody data={growth.data} />
        </div>
      )}
    </div>
  );
}
