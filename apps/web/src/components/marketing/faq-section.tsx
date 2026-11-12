import { ChevronDown } from "lucide-react";

import { PREMIUM_PRICE } from "@/lib/business";
import { TRIAL_DAYS } from "@/lib/pricing";

import { SectionHeading } from "./section-heading";

// Answers restate the round contracts, the Privacy Policy and /pricing; keep them in step.
const QUESTIONS = [
  {
    question: "Do I need to install an app?",
    answer:
      "No. FinBoy works inside WhatsApp. When you want charts and reports, a private web app at finboy.io shows the same diary; sign in with WhatsApp or Google.",
  },
  {
    question: "Does FinBoy read my SMS or connect to my bank?",
    answer:
      "No. It only sees what you send it. You can paste a bank SMS into the chat if you like: account, card and reference numbers are masked before it is read.",
  },
  {
    question: "What if FinBoy gets an entry wrong?",
    answer:
      "Tap ↩️ Undo, ✏️ Amount or 🏷️ Category on its reply. For ₹50,000 or more, a possible duplicate, or an entry that matches a screenshot you sent, it asks before counting it.",
  },
  {
    question: "Which languages does it understand?",
    answer:
      "English, Hindi and Malayalam, typed or (with Premium) spoken. Replies start in English and then follow the language you write in. To choose one, send “english”, “hindi” or “ml”.",
  },
  {
    question: "What is free and what is Premium?",
    answer: `Typed entries, Home, Transactions, Reports, budgets, a savings goal, the today, this week and this month check-ups and asking FinBoy by typing are free. Voice notes and spoken replies, photo and screenshot reading and Google Pay statement import are Premium at ${PREMIUM_PRICE} a month, with your first ${TRIAL_DAYS} days free.`,
  },
  {
    question: "Can I bring in my Google Pay history?",
    answer:
      "Yes, with Premium. Send the statement PDF to FinBoy on WhatsApp or upload it on the web. It is saved only if every row adds up to Google’s own totals.",
  },
  {
    question: "Is FinBoy a bank or an investment app?",
    answer:
      "No. It is a diary of what you record. Its figures come from your entries, not your bank balance, and it never recommends funds or stocks.",
  },
  {
    question: "How do I stop or delete everything?",
    answer:
      "Send STOP to stop all messages and START to turn them back on. To delete your account, open Privacy & data in the web app and choose Delete my account; your records go at once.",
  },
] as const;

export function FaqSection() {
  return (
    <section id="faq" aria-labelledby="faq-title" className="scroll-mt-24 py-14 sm:py-24">
      <div className="mx-auto grid max-w-[1360px] gap-8 px-6 sm:px-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16 lg:px-16">
        <SectionHeading id="faq-title" eyebrow="Questions" title="Before you say hi." />
        <div className="surface divide-y divide-ink/10 rounded-[2rem] px-6 sm:px-8">
          {QUESTIONS.map(({ question, answer }) => (
            <details key={question} className="group py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-ink [&::-webkit-details-marker]:hidden">
                {question}
                <ChevronDown
                  className="size-5 shrink-0 transition-transform group-open:rotate-180 motion-reduce:transition-none"
                  aria-hidden="true"
                />
              </summary>
              <p className="mt-3 text-[0.95rem] leading-relaxed text-ink-soft">{answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
