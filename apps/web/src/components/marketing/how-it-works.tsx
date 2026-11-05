import Link from "next/link";
import type { ReactNode } from "react";

import { PremiumPill } from "@/components/billing/premium-pill";
import { Reveal } from "@/components/motion/reveal";

import { ChatCode } from "./chat-code";
import { ChatPreview } from "./chat-preview";
import { SectionHeading } from "./section-heading";

// What a new number actually sees (docs/signup-round/contract.md, english.py SELF_CONSENT/WELCOME).
const steps: { title: string; body: ReactNode }[] = [
  {
    title: "Send “Hi FinBoy”",
    body: "Tap Start on WhatsApp. The chat opens with the message typed in; tap send.",
  },
  {
    title: "Agree once",
    body: (
      <>
        FinBoy tells you what it writes down — the amount, the date, who you paid and what it was
        for — and that it doesn’t keep your voice notes, photos or messages. Tap ✅ Yes, I agree.
        Tap ❌ No and nothing is kept.
      </>
    ),
  },
  {
    title: "Send what you spent",
    body: (
      <>
        Type it like a note: “chai 20, auto 50, lunch 120”. A voice note, a bill photo or a UPI
        screenshot works too <PremiumPill className="align-middle" />
      </>
    ),
  },
  {
    title: "Check the reply",
    body: "Each entry comes back as ✅ Saved with ↩️ Undo, ✏️ Amount and 🏷️ Category. Send “this month” to see where the money went.",
  },
];

export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" id="how-it-works" className="scroll-mt-24 py-16 sm:py-28">
      <div className="mx-auto grid max-w-[1360px] items-start gap-12 px-6 sm:px-10 lg:grid-cols-[1.1fr_1fr] lg:gap-16 lg:px-16">
        <div>
          <SectionHeading
            id="how-title"
            eyebrow="How it works"
            title="What happens when you say hi."
            description="It all happens in a chat you already use. There is nothing to download and no form to fill in."
          />
          <ol className="mt-8 space-y-5 sm:mt-10 sm:space-y-6">
            {steps.map((step, index) => (
              <li key={step.title} className="flex gap-4">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-ink text-sm font-semibold text-white tabular">
                  {index + 1}
                </span>
                <div>
                  <h3 className="text-lg font-semibold tracking-[-0.02em] text-ink">{step.title}</h3>
                  <p className="mt-1 text-[0.95rem] leading-relaxed text-ink-soft">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-8 space-y-5 sm:mt-10">
            <ChatCode />
            <p className="text-sm leading-relaxed text-ink-soft">
              Prefer a big screen?{" "}
              <Link href="/login" className="font-semibold text-ink underline underline-offset-4">
                Sign in on the web
              </Link>{" "}
              with WhatsApp or Google to see Home, Transactions and Reports.
            </p>
          </div>
        </div>
        <Reveal delay={0.1}>
          <ChatPreview />
        </Reveal>
      </div>
    </section>
  );
}
