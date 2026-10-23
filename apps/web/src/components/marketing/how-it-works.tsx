import { Reveal } from "@/components/motion/reveal";
import { TiltCard } from "@/components/motion/tilt-card";
import { SceneSlot } from "@/components/three/scene-slot";
import type { SceneSpec } from "@/components/three/scene-spec";

import { SectionHeading } from "./section-heading";

const steps: Array<{ number: string; title: string; body: string; spec: SceneSpec; tint: string }> = [
  {
    number: "01",
    title: "Connect Gmail, read-only",
    body: "FinBoy uses sender and keyword filters to scan recent likely financial mail — bank alerts, receipts and bills.",
    spec: { name: "inbox-slab" },
    tint: "from-[#f3efff] to-white",
  },
  {
    number: "02",
    title: "Three alerts, one transaction",
    body: "A bank alert, an order email and an invoice for the same ₹799 become one entry — with all three kept as evidence.",
    spec: { name: "coin-swirl", loop: true },
    tint: "from-[#fdf0fb] to-white",
  },
  {
    number: "03",
    title: "You approve what’s uncertain",
    body: "Low-confidence items wait for one tap. Nothing guessed slips silently into your totals.",
    spec: { name: "check-orb" },
    tint: "from-[#eef2ff] to-white",
  },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" id="how-it-works" className="scroll-mt-24 py-24 sm:py-28">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="how-title"
          eyebrow="How it works"
          title={
            <>
              From inbox to insight,
              <br className="hidden sm:block" /> in three quiet steps.
            </>
          }
          description="No spreadsheets, no manual logging. FinBoy reads the trail your money already leaves and asks you only when it isn’t sure."
        />
        <div className="mt-16 grid gap-6 md:grid-cols-3">
          {steps.map((step, index) => (
            <Reveal key={step.number} delay={index * 0.12}>
              <TiltCard max={3} className="surface h-full overflow-hidden rounded-[2rem]">
                <SceneSlot spec={step.spec} className={`h-64 bg-gradient-to-b ${step.tint}`} />
                <div className="border-t border-black/[0.04] p-7">
                  <span className="font-mono text-xs font-semibold text-violet">/{step.number}</span>
                  <h3 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-ink">{step.title}</h3>
                  <p className="mt-2.5 text-[0.95rem] leading-relaxed text-ink-soft">{step.body}</p>
                </div>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
