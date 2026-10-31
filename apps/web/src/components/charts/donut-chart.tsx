"use client";

import type { ReactNode } from "react";
import { useSvgId } from "@/components/illustrations/kit";
import { donutArcs } from "@/lib/charts";
import { cn } from "@/lib/utils";

export type DonutSlice = { key: string; share: number; color: string };

const SIZE = 220;
const STROKE = 28;
// Room around the ring for the active slice to swell without clipping.
const RADIUS = (SIZE - STROKE) / 2 - 7;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * Part-to-whole at a glance: at most six slices, 2 px apart, with the readout in the middle.
 * The legend table beside it carries every value, so the drawing is hidden from screen readers;
 * hovering or tapping a slice (or focusing its row) makes it the readout.
 */
export function DonutChart({
  slices,
  active,
  onActive,
  children,
}: {
  slices: DonutSlice[];
  active: string | null;
  onActive: (key: string | null) => void;
  children: ReactNode;
}) {
  const sweep = useSvgId("donut-sweep");
  const arcs = donutArcs(
    slices.map((slice) => slice.share),
    2 / CIRCUMFERENCE,
  );
  const center = SIZE / 2;
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[15rem]">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="size-full -rotate-90"
        aria-hidden="true"
        onPointerLeave={() => onActive(null)}
      >
        <defs>
          {/* The ring sweeps in clockwise from the top (CSS, so reduced motion shows it whole). */}
          <mask id={sweep}>
            <circle
              cx={center}
              cy={center}
              r={RADIUS}
              fill="none"
              stroke="#fff"
              strokeWidth={STROKE + 16}
              pathLength={1}
              strokeDasharray="1 1"
              className="animate-sweep"
            />
          </mask>
        </defs>
        <circle cx={center} cy={center} r={RADIUS} fill="none" stroke="rgb(14 16 19 / 0.06)" strokeWidth={STROKE} />
        <g mask={`url(#${sweep})`}>
          {slices.map((slice, index) => {
            const arc = arcs[index] ?? { start: 0, length: 0 };
            const on = active === slice.key;
            return (
              <circle
                key={slice.key}
                cx={center}
                cy={center}
                r={RADIUS}
                fill="none"
                stroke={slice.color}
                strokeWidth={on ? STROKE + 10 : STROKE}
                pathLength={1}
                strokeDasharray={`${arc.length} ${1 - arc.length}`}
                strokeDashoffset={-arc.start}
                className={cn(
                  "cursor-pointer transition-[stroke-width,opacity] duration-300 ease-out-expo",
                  active !== null && !on && "opacity-35",
                )}
                onPointerEnter={() => onActive(slice.key)}
                onClick={() => onActive(on ? null : slice.key)}
              />
            );
          })}
        </g>
      </svg>
      <div className="pointer-events-none absolute inset-0 grid place-items-center p-11 text-center">{children}</div>
    </div>
  );
}
