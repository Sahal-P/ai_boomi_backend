import { BrainCircuit, EyeOff, Lock, Unplug } from "lucide-react";

import { Reveal } from "@/components/motion/reveal";
import { SceneSlot } from "@/components/three/scene-slot";

import { SectionHeading } from "./section-heading";

const PROMISES = [
  { icon: Lock, title: "Read-only Gmail access", body: "FinBoy can’t send, delete or change a single email." },
  { icon: EyeOff, title: "Raw emails are never stored", body: "We keep the amount, merchant and a short evidence snippet — nothing else." },
  { icon: BrainCircuit, title: "Never used for training", body: "Your financial emails don’t train any model, ours or anyone’s." },
  { icon: Unplug, title: "Disconnect means disconnect", body: "Revoke access and delete imported data in two taps." },
] as const;

export function TrustSection() {
  return (
    <section id="trust" aria-labelledby="trust-title" className="scroll-mt-24 py-24 sm:py-28">
      <div className="mx-auto grid max-w-[1360px] items-center gap-12 px-6 sm:px-10 lg:grid-cols-2 lg:px-16">
        <Reveal className="relative order-last lg:order-first">
          <div className="surface overflow-hidden rounded-[2.25rem] bg-[radial-gradient(circle_at_50%_35%,#ffffff,#efeafc)]">
            <SceneSlot spec={{ name: "privacy-vault" }} className="h-[460px] w-full" />
          </div>
        </Reveal>
        <div>
          <SectionHeading
            id="trust-title"
            eyebrow="Privacy by design"
            title="FinBoy doesn’t need your inbox. Just the money in it."
            description="The minimum evidence required to understand your money — and controls that are as easy as connecting."
          />
          <ul className="mt-10 grid gap-4 sm:grid-cols-2">
            {PROMISES.map(({ icon: Icon, title, body }, index) => (
              <li key={title}>
                <Reveal delay={0.08 * index} className="surface h-full rounded-2xl p-5">
                  <span className="grid size-10 place-items-center rounded-xl bg-[linear-gradient(140deg,#efe9ff,#fbe8f8)] text-violet">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-4 font-semibold text-ink">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{body}</p>
                </Reveal>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
