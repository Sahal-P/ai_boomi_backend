"use client";

import { useState } from "react";
import { formatMoney } from "@/lib/api/money";
import { compactMoney, niceTicks } from "@/lib/charts";
import { cn } from "@/lib/utils";

export type ColumnSeries = { key: string; label: string; swatch: string };
export type ColumnGroup = { key: string; label: string; title: string; values: number[]; emphasis: boolean };

/**
 * Paired columns on one ₹ axis: thin bars growing from the baseline with 4 px rounded tops, 2 px
 * apart, and a tooltip per month on hover or tap. The chosen month stays full strength and the
 * others recede. The table view is the accessible equivalent, so the drawing is hidden from
 * screen readers.
 */
export function ColumnChart({
  series,
  groups,
  height = 208,
}: {
  series: ColumnSeries[];
  groups: ColumnGroup[];
  height?: number;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(0, ...groups.flatMap((group) => group.values));
  const ticks = niceTicks(max, 4);
  const top = ticks[ticks.length - 1] || 1;
  return (
    <div aria-hidden="true" className="select-none" onPointerLeave={() => setHover(null)}>
      <div className="relative ml-11" style={{ height }}>
        {ticks.map((tick) => (
          <div key={tick} className="absolute inset-x-0 border-t border-ink/10" style={{ bottom: `${(tick / top) * 100}%` }}>
            <span className="absolute top-0 -left-11 w-9 -translate-y-1/2 text-right text-[11px] text-ink-soft tabular-nums">
              {compactMoney(tick)}
            </span>
          </div>
        ))}
        <div className="absolute inset-0 flex items-end">
          {groups.map((group, groupIndex) => {
            const on = hover === group.key;
            const faded = hover !== null ? !on : !group.emphasis;
            return (
              <div
                key={group.key}
                className="relative flex h-full flex-1 cursor-default items-end justify-center gap-[2px] px-1"
                onPointerEnter={() => setHover(group.key)}
                onClick={() => setHover(on ? null : group.key)}
              >
                {group.values.map((value, index) => (
                  <div
                    key={series[index]?.key ?? index}
                    className={cn(
                      "w-full max-w-[18px] origin-bottom animate-grow-y rounded-t-[4px] transition-opacity duration-300",
                      series[index]?.swatch,
                      faded && "opacity-45",
                    )}
                    style={{
                      height: `${(Math.max(0, value) / top) * 100}%`,
                      animationDelay: `${groupIndex * 60 + index * 30}ms`,
                    }}
                  />
                ))}
                {on && (
                  <div
                    className={cn(
                      "glass pointer-events-none absolute bottom-full z-10 mb-2 w-max min-w-40 rounded-xl px-3 py-2 text-left text-xs",
                      groupIndex === 0
                        ? "left-0"
                        : groupIndex === groups.length - 1
                          ? "right-0"
                          : "left-1/2 -translate-x-1/2",
                    )}
                  >
                    <p className="font-semibold text-ink">{group.title}</p>
                    {series.map((item, index) => (
                      <p key={item.key} className="mt-1 flex items-center gap-2 text-ink-soft">
                        <span className={cn("size-2 shrink-0 rounded-full", item.swatch)} />
                        {item.label}
                        <span className="ml-auto pl-3 font-semibold text-ink tabular-nums">
                          {formatMoney(group.values[index] ?? 0)}
                        </span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="mt-2 ml-11 flex">
        {groups.map((group) => (
          <span
            key={group.key}
            className={cn("flex-1 text-center text-xs", group.emphasis ? "font-semibold text-ink" : "text-ink-soft")}
          >
            {group.label}
          </span>
        ))}
      </div>
    </div>
  );
}
