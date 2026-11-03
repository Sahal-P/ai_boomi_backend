import { Reveal } from "@/components/motion/reveal";
import { TiltCard } from "@/components/motion/tilt-card";
import { SceneSlot } from "@/components/three/scene-slot";

import { SectionHeading } from "./section-heading";

const steps = [
  {
    number: "01",
    title: "Send an entry your way",
    body: "Add an expense by text or voice, share a payment screenshot, or import a supported Google Pay statement.",
  },
  {
    number: "02",
    title: "Check and correct",
    body: "Read the saved entry and fix its amount or category. Use Undo for a mistake; FinBoy asks when it is unsure.",
  },
  {
    number: "03",
    title: "See your spending clearly",
    body: "Review recorded purchases, spending categories and budgets on the web, or ask for a summary in your diary.",
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
                From an entry to insight,
                <br className="hidden sm:block" /> in three quiet steps.
              </>
            }
            description="Keep a diary in a way that fits your day. Check what was recorded, then use your history to understand where the money went."
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
