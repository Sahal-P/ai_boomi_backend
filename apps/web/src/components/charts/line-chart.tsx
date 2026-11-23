"use client";

import { type PointerEvent, useRef, useState } from "react";
import { countLabel, countTicks, nearestPoint, spread } from "@/lib/charts";
import { cn } from "@/lib/utils";

/** `stroke` paints the line (a CSS colour); `swatch` the dots and keys (a background class). */
export type LineSeries = { key: string; label: string; stroke: string; swatch: string };
export type LinePoint = {
  key: string;
  /** Under the point; empty leaves the axis bare there. */
  label: string;
  title: string;
  values: number[];
};

// End labels closer than this would collide; then the legend and tooltip carry the values.
const LABEL_GAP = 14;

/**
 * Counts over time as 2 px lines on one axis, drawn in from the left. A crosshair snaps to the
 * nearest point and one glass tooltip lists every series there; each line ends in a dot with a
 * 2 px ring and its latest value. The table view is the accessible equivalent, so the drawing is
 * hidden from screen readers.
 */
export function LineChart({
  series,
  points,
  height = 208,
  format = (value: number) => value.toLocaleString("en-IN"),
}: {
  series: LineSeries[];
  points: LinePoint[];
  height?: number;
  format?: (value: number) => string;
}) {
  const plot = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(0, ...points.flatMap((point) => point.values));
  const ticks = countTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const xs = spread(points.length);
  const last = points.length - 1;
  const rise = (value: number) => (Math.max(0, value) / top) * 100;
  const ends = series.map((_, index) => rise(points[last]?.values[index] ?? 0));
  const apart = ends.every((end, index) =>
    ends.every((other, at) => at === index || (Math.abs(end - other) * height) / 100 >= LABEL_GAP),
  );
  const shown = hover === null ? null : points[hover];

  function locate(event: PointerEvent<HTMLDivElement>) {
    const box = plot.current?.getBoundingClientRect();
    if (!box?.width) return;
    setHover(nearestPoint((event.clientX - box.left) / box.width, points.length));
  }

  if (!points.length) return null;
  const x = (index: number) => `${(xs[index] ?? 0) * 100}%`;
  return (
    <div aria-hidden="true" className="select-none">
      <div className="relative mr-9 ml-11" style={{ height }}>
        {ticks.map((value) => (
          <div key={value} className="absolute inset-x-0 border-t border-ink/10" style={{ bottom: `${(value / top) * 100}%` }}>
            <span className="absolute top-0 -left-11 w-9 -translate-y-1/2 text-right text-[11px] text-ink-soft tabular-nums">
              {countLabel(value, top)}
            </span>
          </div>
        ))}
        <div className="absolute inset-0 animate-reveal-x">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible">
            {series.map((item, index) => (
              <polyline
                key={item.key}
                points={points
                  .map((point, at) => `${(xs[at] ?? 0) * 100},${100 - rise(point.values[index] ?? 0)}`)
                  .join(" ")}
                fill="none"
                stroke={item.stroke}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
          {series.map((item, index) => (
            <span
              key={item.key}
              className={cn("absolute size-2.5 -translate-x-1/2 translate-y-1/2 rounded-full ring-2 ring-white", item.swatch)}
              style={{ left: x(last), bottom: `${ends[index]}%` }}
            />
          ))}
        </div>
        {apart &&
          series.map((item, index) => (
            <span
              key={item.key}
              className="absolute left-full translate-y-1/2 pl-2 text-xs font-semibold text-ink tabular-nums"
              style={{ bottom: `${ends[index]}%` }}
            >
              {format(points[last]?.values[index] ?? 0)}
            </span>
          ))}
        {shown && hover !== null && (
          <>
            <span className="pointer-events-none absolute inset-y-0 w-px -translate-x-1/2 bg-ink/30" style={{ left: x(hover) }} />
            {series.map((item, index) => (
              <span
                key={item.key}
                className={cn(
                  "pointer-events-none absolute size-2.5 -translate-x-1/2 translate-y-1/2 rounded-full ring-2 ring-white",
                  item.swatch,
                )}
                style={{ left: x(hover), bottom: `${rise(shown.values[index] ?? 0)}%` }}
              />
            ))}
            <div
              className={cn(
                "glass pointer-events-none absolute bottom-full z-10 mb-2 w-max min-w-40 rounded-xl px-3 py-2 text-left text-xs",
                (xs[hover] ?? 0) < 1 / 3 ? "" : (xs[hover] ?? 0) > 2 / 3 ? "-translate-x-full" : "-translate-x-1/2",
              )}
              style={{ left: x(hover) }}
            >
              <p className="font-semibold text-ink">{shown.title}</p>
              {series.map((item, index) => (
                <p key={item.key} className="mt-1 flex items-center gap-2 text-ink-soft">
                  <span className={cn("h-0.5 w-3 shrink-0 rounded-full", item.swatch)} />
                  {item.label}
                  <span className="ml-auto pl-3 font-semibold text-ink tabular-nums">{format(shown.values[index] ?? 0)}</span>
                </p>
              ))}
            </div>
          </>
        )}
        <div
          ref={plot}
          className="absolute inset-0 cursor-crosshair touch-pan-y"
          onPointerMove={locate}
          onPointerDown={locate}
          onPointerLeave={() => setHover(null)}
        />
      </div>
      <div className="relative mt-2 mr-9 ml-11 h-4">
        {points.map((point, index) =>
          point.label ? (
            <span
              key={point.key}
              className={cn(
                "absolute top-0 text-xs whitespace-nowrap text-ink-soft",
                points.length === 1 ? "-translate-x-1/2" : index === 0 ? "" : index === last ? "-translate-x-full" : "-translate-x-1/2",
              )}
              style={{ left: x(index) }}
            >
              {point.label}
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}
