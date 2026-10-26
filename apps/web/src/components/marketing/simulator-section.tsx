import { AlertCircle } from "lucide-react";

import { AnimatedAmount } from "@/components/motion/animated-amount";
import { Reveal } from "@/components/motion/reveal";
import { SceneSlot } from "@/components/three/scene-slot";

import { SectionHeading } from "./section-heading";

// Demo truth table (docs/phase1/contract.md §8), in paise.
const LINES = [
  { label: "Tracked income", amountMinor: 6_200_000, sign: "+" },
  { label: "Confirmed outflows", amountMinor: 3_742_000, sign: "−" },
  { label: "Upcoming commitments", amountMinor: 980_000, sign: "−" },
  { label: "Proposed monthly SIP", amountMinor: 500_000, sign: "−" },
] as const;

const COLUMNS = ["Income", "Spent", "Bills", "SIP", "Left"] as const;

export function SimulatorSection() {
  return (
    <section id="simulator" aria-labelledby="simulator-title" className="scroll-mt-24 py-24 sm:py-28">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="simulator-title"
          eyebrow="Cash-flow simulator"
          title={<>“Enikk ₹5,000 SIP start cheyyan pattumo?”</>}
          description="Ask what-if questions about your own money. FinBoy models cash flow from verified records — it never picks funds or stocks for you."
        />
        <div className="mt-14 grid items-stretch gap-6 lg:grid-cols-[1fr_1.1fr]">
          <Reveal className="surface rounded-[2rem] p-7 sm:p-9">
            <p className="text-sm font-semibold text-ink-soft">Synthetic demo · ₹5,000 monthly saving · October</p>
            <dl className="mt-6 divide-y divide-black/[0.05]">
              {LINES.map((line) => (
                <div key={line.label} className="flex items-baseline justify-between py-3.5">
                  <dt className="text-[0.95rem] text-ink-soft">{line.label}</dt>
                  <dd className="text-lg font-semibold text-ink">
                    <AnimatedAmount amountMinor={line.amountMinor} prefix={`${line.sign} `} />
                  </dd>
                </div>
              ))}
            </dl>
            <div className="solid-hero mt-2 flex items-baseline justify-between rounded-2xl px-5 py-5">
              <p className="font-semibold">Estimated remaining</p>
              <AnimatedAmount amountMinor={978_000} className="text-4xl font-semibold tracking-[-0.03em]" duration={2} />
            </div>
            <p className="mt-5 flex items-start gap-2 rounded-xl bg-amber-50 px-3.5 py-2.5 text-sm text-amber-900">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />2 transactions are awaiting your confirmation.
            </p>
            <p className="mt-5 text-xs leading-relaxed text-ink-subtle">
              This models cash flow from FinBoy's tracked records. It is not a recommendation to purchase any security.
            </p>
          </Reveal>
          <Reveal delay={0.12} className="surface relative flex flex-col overflow-hidden rounded-[2rem] bg-[radial-gradient(circle_at_50%_32%,rgb(255_255_255/0.9),transparent_68%)]">
            <SceneSlot spec={{ name: "coin-stack", values: [1, 0.6, 0.16, 0.08, 0.16] }} className="min-h-[380px] w-full flex-1" />
            <ul className="mx-auto grid w-full max-w-[34rem] grid-cols-5 border-t border-black/[0.05] px-4 py-4 text-center text-xs font-semibold text-ink-soft">
              {COLUMNS.map((column) => (
                <li key={column}>{column}</li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
