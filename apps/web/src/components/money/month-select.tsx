"use client";

import { isRange, monthKey, type MonthRange, type Period } from "@/lib/api/money";
import { monthLabel, rangeLabel, recentMonths, type Month } from "@/lib/dates";
import { cn } from "@/lib/utils";

const key = (month: Month) => `${month.year}-${month.month}`;
const LAST = [3, 6, 12] as const;

function lastMonths(count: number, current: Month): MonthRange {
  const index = current.year * 12 + current.month - count;
  return { from: { year: Math.floor(index / 12), month: (index % 12) + 1 }, to: current };
}

const rangeValue = (range: MonthRange) => `range:${monthKey(range.from)}:${monthKey(range.to)}`;

/**
 * The one period control. Home picks this month or one of the 17 before it; Reports also picks the
 * last 3, 6 or 12 months, and keeps an imported statement's months as their own option. A link that
 * names the current month shows as "This month", and an older one gets its own option, never a blank.
 */
export function MonthSelect({
  id,
  period,
  onChange,
  ranges = false,
  className,
}: {
  id: string;
  period: Period;
  onChange: (period: Period) => void;
  ranges?: boolean;
  className?: string | undefined;
}) {
  const [current, ...earlier] = recentMonths(18);
  const presets = current && ranges ? LAST.map((count) => ({ count, range: lastMonths(count, current) })) : [];
  const preset = isRange(period) ? presets.find((item) => rangeValue(item.range) === rangeValue(period)) : undefined;
  const custom = isRange(period) && ranges && !preset ? period : null;
  const chosen = !isRange(period) && period && current && key(period) !== key(current) ? period : null;
  const options = chosen && !earlier.some((item) => key(item) === key(chosen)) ? [...earlier, chosen] : earlier;
  const value = preset ? rangeValue(preset.range) : custom ? rangeValue(custom) : chosen ? key(chosen) : "";
  return (
    <>
      <label className="sr-only" htmlFor={id}>
        {ranges ? "Period" : "Month"}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => {
          const next = event.target.value;
          const range = /^range:(\d{4})-(\d{2}):(\d{4})-(\d{2})$/.exec(next);
          if (range) {
            const [, fromYear, fromMonth, toYear, toMonth] = range.map(Number);
            onChange({ from: { year: fromYear ?? 0, month: fromMonth ?? 0 }, to: { year: toYear ?? 0, month: toMonth ?? 0 } });
            return;
          }
          const [year, month] = next.split("-").map(Number);
          onChange(year && month ? { year, month } : null);
        }}
        className={cn("field field-select h-11 min-w-0 rounded-full pl-4 text-sm font-semibold", className)}
      >
        <option value="">This month</option>
        {presets.map((item) => (
          <option key={item.count} value={rangeValue(item.range)}>
            Last {item.count} months
          </option>
        ))}
        {custom && <option value={rangeValue(custom)}>{rangeLabel(custom.from, custom.to)}</option>}
        {options.map((item) => (
          <option key={key(item)} value={key(item)}>
            {monthLabel(item.year, item.month)}
          </option>
        ))}
      </select>
    </>
  );
}
