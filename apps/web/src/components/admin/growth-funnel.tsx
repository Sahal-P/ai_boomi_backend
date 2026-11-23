import { count } from "@/components/admin/admin-bits";
import type { GrowthFunnel as Funnel } from "@/lib/api/admin";
import { funnelSteps } from "@/lib/growth";
import { cn } from "@/lib/utils";

// Steps 3–7 of the blue ramp, darker the further in: an ordinal ramp, validated on glass (its
// light end is 2.02:1). The words carry every number; the bars only repeat them.
const FILLS = ["bg-chart-seq-3", "bg-chart-seq-4", "bg-chart-seq-5", "bg-chart-seq-6", "bg-chart-seq-7"];

/**
 * From a page visit to a first record (docs/admin-growth/contract.md): one bar per step, scaled to
 * the widest, with each step's share of the step before and of page opens.
 */
export function GrowthFunnel({ funnel }: { funnel: Funnel }) {
  const steps = funnelSteps(funnel);
  const widest = Math.max(1, ...steps.map((step) => step.count));
  return (
    <>
      <ol className="space-y-4">
        {steps.map((step, index) => (
          <li key={step.key}>
            <p className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
              <span className="font-medium">{step.label}</span>
              <span className="font-semibold tabular-nums">{count(step.count)}</span>
            </p>
            <span aria-hidden="true" className="mt-1.5 block h-2">
              <span
                className={cn("block h-full origin-left animate-grow-x rounded-r-[4px]", FILLS[index])}
                style={{
                  width: `${Math.max(step.count > 0 ? 1 : 0, (step.count / widest) * 100)}%`,
                  animationDelay: `${index * 70}ms`,
                }}
              />
            </span>
            <p className="mt-1 text-xs text-ink-soft tabular-nums">
              {step.ofPrevious === null
                ? "Every page visit with the WhatsApp button"
                : `${step.ofPrevious} of the step before · ${step.ofOpened} of page visits`}
            </p>
          </li>
        ))}
      </ol>
      {funnel.direct_signed_up > 0 && (
        <p className="mt-5 text-sm leading-relaxed text-ink-soft">
          Also {count(funnel.direct_signed_up)} signed up with no page visit (a shared number, QR code or an old
          link): {count(funnel.direct_agreed)} agreed and {count(funnel.direct_first_record)} made a first record.
        </p>
      )}
    </>
  );
}
