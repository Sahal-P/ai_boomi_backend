import { EyeOff, Lock, ScanText, Trash2 } from "lucide-react";
import Link from "next/link";

import { Reveal } from "@/components/motion/reveal";

import { SectionHeading } from "./section-heading";

// Each line restates the Privacy Policy, the consent card or the Contact page; nothing beyond them.
const FACTS = [
  {
    icon: Lock,
    title: "It only sees what you send",
    body: "No bank login and no access to your SMS. FinBoy never asks for a card number, UPI PIN or OTP.",
  },
  {
    icon: EyeOff,
    title: "Your messages aren’t kept",
    body: "FinBoy writes down the amount, the date, who you paid and what it was for. Your WhatsApp messages, voice notes, photos, screenshots, statement PDFs and their transcripts aren’t kept.",
  },
  {
    icon: ScanText,
    title: "Named services, no ads",
    body: "AI services such as OpenAI read an entry only to process it, and the Privacy Policy names every one. FinBoy never sells your data and never shows ads.",
  },
  {
    icon: Trash2,
    title: "Leave whenever you like",
    body: "Export your records from Privacy & data. Send STOP to stop messages. Delete your account and your records go at once.",
  },
] as const;

export function TrustSection() {
  return (
    <section id="privacy" aria-labelledby="privacy-title" className="scroll-mt-24 py-14 sm:py-24">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="privacy-title"
          eyebrow="Privacy"
          title="FinBoy keeps the record, not your messages."
          description="Only you can see your records. This is what FinBoy sees, keeps and lets you remove."
        />
        <ul className="mt-8 grid gap-3 sm:mt-12 sm:grid-cols-2 sm:gap-4 xl:grid-cols-4">
          {FACTS.map(({ icon: Icon, title, body }, index) => (
            <li key={title}>
              <Reveal delay={0.08 * index} className="surface h-full rounded-2xl p-5 sm:p-6">
                <span className="grid size-10 place-items-center rounded-xl bg-white/80 text-ink ring-1 ring-ink/[0.06]">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <h3 className="mt-4 font-semibold text-ink">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{body}</p>
              </Reveal>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-sm text-ink-soft">
          <Link href="/privacy-policy" className="font-semibold text-ink underline underline-offset-4">
            Read the Privacy Policy
          </Link>{" "}
          for every provider, what is kept and for how long.
        </p>
      </div>
    </section>
  );
}
