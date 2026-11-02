import { Reveal } from "@/components/motion/reveal";
import { TiltCard } from "@/components/motion/tilt-card";
import { SceneSlot } from "@/components/three/scene-slot";

import { SectionHeading } from "./section-heading";

const steps = [
  {
    number: "01",
    title: "Connect Gmail, read-only",
    body: "FinBoy uses sender and keyword filters to scan recent likely financial mail — bank alerts, receipts and bills.",
  },
  {
    number: "02",
    title: "Three alerts, one transaction",
    body: "A bank alert, an order email and an invoice for the same ₹799 become one entry — with all three kept as evidence.",
  },
  {
    number: "03",
    title: "You approve what’s uncertain",
    body: "Low-confidence items wait for one tap. Nothing guessed slips silently into your totals.",
  },
] as const;

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" id="how-it-works" className="scroll-mt-24 py-24 sm:py-28">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <div className="grid items-center gap-10 lg:grid-cols-[1.15fr_1fr] lg:gap-16">
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
          {/* Three sources merge into one stack: step 02, the heart of FinBoy. */}
          <Reveal delay={0.12} className="surface overflow-hidden rounded-[2rem]">
            <SceneSlot
              spec={{ name: "coin-swirl", loop: true }}
              className="h-64 bg-gradient-to-b from-field-warm/70 to-white/70 sm:h-72 lg:h-80"
            />
          </Reveal>
        </div>
        <ol className="mt-12 grid gap-6 md:grid-cols-3">
          {steps.map((step, index) => (
            <li key={step.number}>
              <Reveal delay={index * 0.12} className="h-full">
                <TiltCard max={3} className="surface h-full rounded-[2rem] p-7">
                  <span className="font-mono text-xs font-semibold text-ink-soft">/{step.number}</span>
                  <h3 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-ink">{step.title}</h3>
                  <p className="mt-2.5 text-[0.95rem] leading-relaxed text-ink-soft">{step.body}</p>
                </TiltCard>
              </Reveal>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
