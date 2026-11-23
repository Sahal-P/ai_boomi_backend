import type { Category } from "./api/money.ts";

// Presentation maths for the Reports charts. Totals always come from the API; nothing here
// recalculates money, it only places and labels what the engine returned.

export type CategoryTotal = { category: Category; amount_minor: number; transaction_count: number };
export type Slice = { key: Category | "rest"; amount_minor: number; share: number };

/**
 * Spending by category for a donut: positive totals only, largest first, at most `keep` slices
 * plus one "rest" slice for the tail (never a tail of one). Net refunds are left out of the
 * drawing and returned separately.
 */
export function foldSlices(
  rows: readonly CategoryTotal[],
  keep = 5,
): { slices: Slice[]; spending: CategoryTotal[]; refunds: CategoryTotal[]; total_minor: number } {
  const spending = rows.filter((row) => row.amount_minor > 0).sort((a, b) => b.amount_minor - a.amount_minor);
  const refunds = rows.filter((row) => row.amount_minor < 0);
  const total = spending.reduce((sum, row) => sum + row.amount_minor, 0);
  if (!total) return { slices: [], spending, refunds, total_minor: 0 };
  const head = spending.length > keep + 1 ? spending.slice(0, keep) : spending;
  const slices: Slice[] = head.map((row) => ({
    key: row.category,
    amount_minor: row.amount_minor,
    share: row.amount_minor / total,
  }));
  const tail = spending.slice(head.length);
  if (tail.length) {
    const amount = tail.reduce((sum, row) => sum + row.amount_minor, 0);
    slices.push({ key: "rest", amount_minor: amount, share: amount / total });
  }
  return { slices, spending, refunds, total_minor: total };
}

/** "42%", or "<1%" for a sliver that would otherwise read as nothing. */
export function sharePercent(share: number): string {
  if (share > 0 && share < 0.005) return "<1%";
  return `${Math.round(share * 100)}%`;
}

/**
 * Each slice's arc as fractions of the circle (start, length), with `gap` left before the next
 * slice so neighbours never touch. A lone slice is the whole ring.
 */
export function donutArcs(shares: readonly number[], gap: number): { start: number; length: number }[] {
  let start = 0;
  return shares.map((share) => {
    const arc = { start, length: shares.length > 1 ? Math.max(share - gap, share / 2) : share };
    start += share;
    return arc;
  });
}

/** Round axis steps (1, 2, 2.5 or 5 × 10ⁿ) from 0 up to at least `max`, about `count` of them. */
export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * power).find((value) => value >= raw) ?? 10 * power;
  return Array.from({ length: Math.ceil(max / step) + 1 }, (_, index) => index * step);
}

const compact = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Axis labels in Indian units: ₹500, ₹10K, ₹1.2L, ₹2.5Cr. */
export const compactMoney = (minor: number) => compact.format(minor / 100);

/** Days a monthly total covers so far: up to `asOf` for the running month, else the whole month. */
export function daysCounted(start: string, end: string, asOf: string): number {
  const last = asOf < end ? asOf : end;
  const days = Math.round((Date.parse(`${last}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000) + 1;
  return Math.max(1, days);
}

/**
 * Whole-number axis steps (1, 2 or 5 × 10ⁿ, and 2.5 × 10ⁿ from 25 up) from 0 to at least `max`,
 * about `count` of them: counts are never drawn against a half.
 */
export function countTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const raw = Math.max(1, max / count);
  const power = 10 ** Math.floor(Math.log10(raw));
  const factors = power >= 10 ? [1, 2, 2.5, 5, 10] : [1, 2, 5, 10];
  const step = factors.map((factor) => factor * power).find((value) => value >= raw) ?? 10 * power;
  return Array.from({ length: Math.ceil(max / step) + 1 }, (_, index) => index * step);
}

const compactNumber = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });

/** A count on an axis reaching `top`: in full below 10,000 (2,500), compact from there (12K, 1.2L). */
export const countLabel = (value: number, top: number) =>
  top < 10_000 ? value.toLocaleString("en-IN") : compactNumber.format(value);

/** Where each of `count` points sits across a chart, from 0 to 1; a lone point sits in the middle. */
export function spread(count: number): number[] {
  if (count === 1) return [0.5];
  return Array.from({ length: count }, (_, index) => index / (count - 1));
}

/** The nearest of `count` spread points to `x` (0 to 1 across the chart). */
export function nearestPoint(x: number, count: number): number {
  if (count <= 1) return 0;
  return Math.min(count - 1, Math.max(0, Math.round(x * (count - 1))));
}
