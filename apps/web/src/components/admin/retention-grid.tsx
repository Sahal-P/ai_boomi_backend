"use client";

import { useState } from "react";
import { count } from "@/components/admin/admin-bits";
import type { Growth } from "@/lib/api/admin";
import { cohortTitle, percentOf, rampStep } from "@/lib/growth";
import { cn } from "@/lib/utils";

// The blue sequential ramp, lightest for few. Ink text on steps 1–4 (≥ 5.24:1) and white on 5–7
// (≥ 5.39:1), so every share stays readable on its own cell.
const CELLS = [
  "bg-ink/[0.04] text-ink-soft",
  "bg-chart-seq-1 text-ink",
  "bg-chart-seq-2 text-ink",
  "bg-chart-seq-3 text-ink",
  "bg-chart-seq-4 text-ink",
  "bg-chart-seq-5 text-white",
  "bg-chart-seq-6 text-white",
  "bg-chart-seq-7 text-white",
];

type Cell = { cohort: string; step: number; active: number; households: number; running: boolean };

/**
 * Coming back (docs/admin-growth/contract.md): households by the week or month they agreed, and
 * the share active in each one after. A real table; on phones it scrolls sideways inside its card
 * with the joining column fixed. Pointing at a cell spells it out underneath.
 */
export function RetentionGrid({ cohorts, unit }: { cohorts: Growth["cohorts"]; unit: Growth["cohort_unit"] }) {
  const [shown, setShown] = useState<Cell | null>(null);
  const columns = Math.max(0, ...cohorts.map((cohort) => cohort.active.length));
  const name = unit === "week" ? "Week" : "Month";
  if (!cohorts.length) return <p className="text-sm text-ink-soft">Nobody has agreed in this period yet.</p>;
  return (
    <>
      <div className="-mx-1 overflow-x-auto px-1 pb-1" onPointerLeave={() => setShown(null)}>
        <table className="w-full min-w-max border-separate border-spacing-[2px] text-xs">
          <caption className="sr-only">
            Of the households that agreed each {unit}, the share active in each {unit} after
          </caption>
          <thead>
            <tr className="text-ink-soft">
              <th scope="col" className="sticky left-0 z-[1] bg-white/85 py-1.5 pr-3 text-left font-semibold">
                Agreed
              </th>
              <th scope="col" className="px-2 py-1.5 text-right font-semibold">
                Households
              </th>
              {Array.from({ length: columns }, (_, step) => (
                <th key={step} scope="col" className="min-w-12 px-1 py-1.5 text-center font-semibold whitespace-nowrap">
                  {name} {step}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cohorts.map((cohort) => (
              <tr key={cohort.start}>
                <th
                  scope="row"
                  className="sticky left-0 z-[1] bg-white/85 py-1.5 pr-3 text-left font-medium whitespace-nowrap"
                >
                  {cohortTitle(cohort.start, unit)}
                </th>
                <td className="px-2 py-1.5 text-right font-semibold tabular-nums">{count(cohort.households)}</td>
                {Array.from({ length: columns }, (_, step) => {
                  const active = cohort.active[step];
                  // Not reached yet: this cohort's later weeks or months are still to come.
                  if (active === undefined) return <td key={step} />;
                  if (!cohort.households) {
                    return (
                      <td key={step} className="text-center text-ink-soft">
                        —
                      </td>
                    );
                  }
                  const running = step === cohort.active.length - 1;
                  const share = percentOf(active, cohort.households);
                  const cell = { cohort: cohort.start, step, active, households: cohort.households, running };
                  const on = shown?.cohort === cohort.start && shown.step === step;
                  return (
                    <td
                      key={step}
                      className={cn(
                        "h-9 min-w-12 rounded-[4px] px-1 text-center font-semibold tabular-nums transition-[filter]",
                        CELLS[rampStep(active / cohort.households)],
                        on && "brightness-110 saturate-150",
                      )}
                      onPointerEnter={() => setShown(cell)}
                      onClick={() => setShown(on ? null : cell)}
                    >
                      <span aria-hidden="true">{share}</span>
                      <span className="sr-only">
                        {count(active)} of {count(cohort.households)} active, {share}
                        {running ? ", so far" : ""}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p aria-hidden="true" className="mt-3 min-h-5 text-xs text-ink-soft tabular-nums">
        {shown
          ? `${cohortTitle(shown.cohort, unit)}, ${name.toLowerCase()} ${shown.step}${shown.running ? " (so far)" : ""}: ${count(
              shown.active,
            )} of ${count(shown.households)} households active, ${percentOf(shown.active, shown.households)}`
          : `Point at a share to see its households. The last share in each row is the running ${unit}, so far.`}
      </p>
      <div aria-hidden="true" className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
        <span>0%</span>
        <span className="flex gap-[2px]">
          {CELLS.slice(1).map((cell) => (
            <span key={cell} className={cn("h-3 w-6 rounded-[3px]", cell)} />
          ))}
        </span>
        <span>100% active</span>
      </div>
    </>
  );
}
