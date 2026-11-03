import { BrainCircuit, EyeOff, Lock, Unplug } from "lucide-react";

import { Reveal } from "@/components/motion/reveal";

import { SectionHeading } from "./section-heading";

const PROMISES = [
  {
    icon: Lock,
    title: "A private account",
    body: "Your household records sit behind sign-in. Share only the entries and documents you want to record.",
  },
  {
    icon: EyeOff,
    title: "Original media is not kept",
    body: "FinBoy keeps structured records rather than your original audio, images or statement PDFs.",
  },
  {
    icon: BrainCircuit,
    title: "Processing explained",
    body: "The Privacy Policy explains which providers process your entries and the controls available for your data.",
  },
  {
    icon: Unplug,
    title: "Controls for your records",
    body: "Review your records, export your data and use Privacy & data to manage what is retained.",
  },
] as const;

export function TrustSection() {
  return (
    <section id="trust" aria-labelledby="trust-title" className="scroll-mt-24 py-24 sm:py-28">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="trust-title"
          eyebrow="Privacy by design"
          title="Your records. Your controls."
          description="Know what you share, how it is processed and how to manage the records in your account."
        />
        <ul className="mt-12 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {PROMISES.map(({ icon: Icon, title, body }, index) => (
            <li key={title}>
              <Reveal delay={0.08 * index} className="surface h-full rounded-2xl p-6">
                <span className="grid size-10 place-items-center rounded-xl bg-white/80 text-ink ring-1 ring-ink/[0.06]">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <h3 className="mt-4 font-semibold text-ink">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{body}</p>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
