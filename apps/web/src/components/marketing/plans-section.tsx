import { Check } from "lucide-react";
import Link from "next/link";

import { PREMIUM_PRICE } from "@/lib/business";
import { FREE_FEATURES, PREMIUM_FEATURES, TRIAL_DAYS } from "@/lib/pricing";

import { SectionHeading } from "./section-heading";

function Features({ items }: { items: readonly string[] }) {
  return (
    <ul className="mt-6 space-y-2.5 text-sm">
      {items.map((text) => (
        <li key={text} className="flex items-start gap-2.5">
          <Check className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {text}
        </li>
      ))}
    </ul>
  );
}

/** The published plans, word for word the lists on /pricing (lib/pricing.ts). */
export function PlansSection() {
  return (
    <section id="plans" aria-labelledby="plans-title" className="scroll-mt-24 py-14 sm:py-24">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="plans-title"
          eyebrow="Plans"
          title="Typing is free. Premium listens, reads and answers."
          description={`Every new household gets its first ${TRIAL_DAYS} days of Premium. No card needed to start.`}
        />
        <div className="mt-8 grid max-w-4xl gap-3 sm:mt-12 sm:gap-4 md:grid-cols-2">
          <div className="surface rounded-[2rem] p-6 sm:p-7">
            <h3 className="text-lg font-semibold text-ink">Free</h3>
            <p className="mt-2 text-4xl font-extrabold tracking-[-0.04em] text-ink tabular">₹0</p>
            <p className="text-sm text-ink-soft">For as long as you like.</p>
            <div className="text-ink">
              <Features items={FREE_FEATURES} />
            </div>
          </div>
          <div className="moment rounded-[2rem] p-6 sm:p-7">
            <h3 className="text-lg font-semibold">Premium</h3>
            <p className="mt-2 text-4xl font-extrabold tracking-[-0.04em] tabular">
              {PREMIUM_PRICE}
              <span className="text-base font-semibold tracking-normal"> a month</span>
            </p>
            <p className="text-sm font-semibold">First {TRIAL_DAYS} days free. No card needed to start.</p>
            <Features items={PREMIUM_FEATURES} />
          </div>
        </div>
        <p className="mt-6 max-w-2xl text-sm leading-relaxed text-ink-soft">
          When your {TRIAL_DAYS} days end you move to Free unless you choose Premium, and nothing you
          recorded is locked away. Premium is paid on PayU’s secure page by UPI, card or net banking,
          with no fees added.{" "}
          <Link href="/pricing" className="font-semibold text-ink underline underline-offset-4">
            Pricing, renewals and refunds
          </Link>
        </p>
      </div>
    </section>
  );
}
