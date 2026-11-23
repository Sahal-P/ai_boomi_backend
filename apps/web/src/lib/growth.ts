import type { Growth, GrowthFunnel, GrowthPeriod, GrowthPoint } from "./api/admin.ts";
import { sharePercent } from "./charts.ts";

// Words and places for the admin Growth page (docs/admin-growth/contract.md). Every count comes
// from the API; nothing here works one out.

export type GrowthUnit = Growth["unit"];

export const PERIOD_LABELS: Record<GrowthPeriod, string> = {
  "30d": "30 days",
  "12w": "12 weeks",
  "12m": "12 months",
};
/** How each period is broken up. */
export const PERIOD_UNITS: Record<GrowthPeriod, GrowthUnit> = { "30d": "day", "12w": "week", "12m": "month" };
const BEFORE: Record<GrowthPeriod, string> = {
  "30d": "the 30 days before",
  "12w": "the 12 weeks before",
  "12m": "the 12 months before",
};

const dayMonth = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const weekday = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short" });
const monthShort = new Intl.DateTimeFormat("en-IN", { month: "short" });
const monthYear = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" });

function calendar(value: string): Date {
  const [year, month, date] = value.split("-").map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, date ?? 1);
}

/** Under a point: "24 Nov" for a day or a week (its Monday), "Nov" for a month. */
export function axisLabel(start: string, unit: GrowthUnit): string {
  return (unit === "month" ? monthShort : dayMonth).format(calendar(start));
}

/** A point's heading: "Tue, 24 Nov", "Week of 17 Nov" or "November 2026", "so far" while it runs. */
export function pointTitle(point: Pick<GrowthPoint, "start" | "partial">, unit: GrowthUnit): string {
  const date = calendar(point.start);
  const title =
    unit === "day" ? weekday.format(date) : unit === "week" ? `Week of ${dayMonth.format(date)}` : monthYear.format(date);
  return point.partial ? `${title} (so far)` : title;
}

/** A cohort's row heading: "Week of 17 Nov" or "November 2026". */
export function cohortTitle(start: string, unit: Growth["cohort_unit"]): string {
  return unit === "week" ? `Week of ${dayMonth.format(calendar(start))}` : monthYear.format(calendar(start));
}

/** Whether the axis labels point `index` of `count`: all of up to 12, else about 6, ending on the last. */
export function showsLabel(index: number, count: number): boolean {
  if (count <= 12) return true;
  return (count - 1 - index) % Math.ceil(count / 6) === 0;
}

/** "42%" of a whole, or a dash when there is no whole. */
export function percentOf(part: number, whole: number): string {
  return whole > 0 ? sharePercent(part / whole) : "—";
}

export type Direction = "up" | "down" | "same";

/** How this period compares with the same length of time just before it. */
export function comparison(now: number, before: number, period: GrowthPeriod): { direction: Direction; text: string } {
  if (now === before) return { direction: "same", text: `Same as ${BEFORE[period]}` };
  const gap = Math.abs(now - before).toLocaleString("en-IN");
  return now > before
    ? { direction: "up", text: `${gap} more than ${BEFORE[period]}` }
    : { direction: "down", text: `${gap} fewer than ${BEFORE[period]}` };
}

/** "+3", "−1" or "0". */
export function signed(value: number): string {
  if (value === 0) return "0";
  return `${value > 0 ? "+" : "−"}${Math.abs(value).toLocaleString("en-IN")}`;
}

/** The ramp step for a share of a cohort: 1 (lightest) to 7 (darkest), or 0 when nobody. */
export function rampStep(share: number): number {
  if (!(share > 0)) return 0;
  return Math.min(7, Math.max(1, Math.ceil(share * 7)));
}

export type FunnelStep = { key: string; label: string; count: number; ofPrevious: string | null; ofOpened: string | null };

/** The way in, step by step, with each step's share of the one before and of page opens. */
export function funnelSteps(funnel: GrowthFunnel): FunnelStep[] {
  const steps = [
    ["opened", "Opened a page", funnel.opened],
    ["tapped", "Tapped WhatsApp", funnel.tapped],
    ["signed_up", "Signed up", funnel.signed_up],
    ["agreed", "Agreed", funnel.agreed],
    ["first_record", "Made a first record", funnel.first_record],
  ] as const;
  return steps.map(([key, label, value], index) => ({
    key,
    label,
    count: value,
    ofPrevious: index === 0 ? null : percentOf(value, steps[index - 1]?.[2] ?? 0),
    ofOpened: index === 0 ? null : percentOf(value, funnel.opened),
  }));
}
