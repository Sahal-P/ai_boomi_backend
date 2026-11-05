import { Reveal } from "@/components/motion/reveal";

import { SectionHeading } from "./section-heading";

// The saved card's buttons and the ask-first rules (docs/money-manager-round/contract.md).
const FIXES = [
  {
    glyph: "↩️",
    title: "Undo",
    body: "Takes the entry out of your records. Changed your mind? Tap ↩️ Put it back.",
  },
  {
    glyph: "✏️",
    title: "Amount",
    body: "Say or type the right amount, like 400, and the saved card comes back corrected.",
  },
  {
    glyph: "🏷️",
    title: "Category",
    body: "Pick from your most-used categories. FinBoy remembers the choice for that payee next time.",
  },
  {
    glyph: "💡",
    title: "It asks first when unsure",
    body: "For ₹50,000 or more, a possible duplicate, or an entry that matches a screenshot or bill you already sent, FinBoy asks “Is this right?” before counting it.",
  },
] as const;

export function CorrectionsSection() {
  return (
    <section id="corrections" aria-labelledby="corrections-title" className="scroll-mt-24 py-14 sm:py-24">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="corrections-title"
          eyebrow="When it gets something wrong"
          title="Every saved entry can be undone or fixed in one tap."
          description="Voice notes and photos can be misread. So every reply carries its own buttons, and the To review tab on the web lists anything still waiting for you."
        />
        <ul className="mt-8 grid gap-3 sm:mt-12 sm:grid-cols-2 sm:gap-4 xl:grid-cols-4">
          {FIXES.map((fix, index) => (
            <li key={fix.title}>
              <Reveal delay={0.08 * index} className="surface h-full rounded-2xl p-5 sm:p-6">
                <span aria-hidden="true" className="grid size-10 place-items-center rounded-xl bg-white/80 text-lg ring-1 ring-ink/[0.06]">
                  {fix.glyph}
                </span>
                <h3 className="mt-4 font-semibold text-ink">{fix.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{fix.body}</p>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
