"use client";

import type { Period } from "@/lib/api/money";
import { monthLabel, recentMonths, type Month } from "@/lib/dates";
import { cn } from "@/lib/utils";

const key = (month: Month) => `${month.year}-${month.month}`;

/**
 * The one month control (Home, Reports): this month or one of the 17 before it. A link that names
 * the current month shows as "This month", and an older one gets its own option, never a blank.
 */
export function MonthSelect({
  id,
  period,
  onChange,
  className,
}: {
  id: string;
  period: Period;
  onChange: (period: Period) => void;
  className?: string | undefined;
}) {
  const [current, ...earlier] = recentMonths(18);
  const chosen = period && current && key(period) !== key(current) ? period : null;
  const options = chosen && !earlier.some((item) => key(item) === key(chosen)) ? [...earlier, chosen] : earlier;
  return (
    <>
      <label className="sr-only" htmlFor={id}>
        Month
      </label>
      <select
        id={id}
        value={chosen ? key(chosen) : ""}
        onChange={(event) => {
          const [year, month] = event.target.value.split("-").map(Number);
          onChange(year && month ? { year, month } : null);
        }}
        className={cn("field field-select h-11 min-w-0 rounded-full pl-4 text-sm font-semibold", className)}
      >
        <option value="">This month</option>
        {options.map((item) => (
          <option key={key(item)} value={key(item)}>
            {monthLabel(item.year, item.month)}
          </option>
        ))}
      </select>
    </>
  );
}
