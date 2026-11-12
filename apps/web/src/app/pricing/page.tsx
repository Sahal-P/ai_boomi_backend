import { Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage } from "@/components/legal/legal-page";
import { BUSINESS, PREMIUM_PRICE } from "@/lib/business";
import { FREE_FEATURES, PREMIUM_FEATURES, TRIAL_DAYS } from "@/lib/pricing";

export const metadata: Metadata = {
  robots: { index: true, follow: true },
  alternates: { canonical: "/pricing" },
  title: "Pricing",
  description: `FinBoy is free to use. Premium adds voice, photo reading and statement import for ${PREMIUM_PRICE} a month, with the first ${TRIAL_DAYS} days free.`,
};

function Features({ items }: { items: readonly string[] }) {
  return (
    <div role="list" className="mt-5 space-y-2.5 text-sm">
      {items.map((text) => (
        <p role="listitem" key={text} className="mt-0! flex items-start gap-2.5">
          <Check className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {text}
        </p>
      ))}
    </div>
  );
}

export default function PricingPage() {
  return (
    <LegalPage title="Pricing" updated="2 November 2026">
      <p>
        FinBoy is free to use. Premium adds the parts that listen, read and speak, for{" "}
        {PREMIUM_PRICE} a month — and every new household gets its first {TRIAL_DAYS} days of
        Premium free.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <section aria-labelledby="free-plan" className="rounded-3xl bg-well p-6 ring-1 ring-ink/5">
          <h2 id="free-plan" className="mt-0!">
            Free
          </h2>
          <p className="text-4xl font-extrabold tracking-[-0.04em] tabular-nums">₹0</p>
          <p className="text-sm text-ink-soft">For as long as you like.</p>
          <Features items={FREE_FEATURES} />
        </section>
        <section aria-labelledby="premium-plan" className="moment rounded-3xl p-6">
          <h2 id="premium-plan" className="mt-0!">
            Premium
          </h2>
          <p className="text-4xl font-extrabold tracking-[-0.04em] tabular-nums">
            {PREMIUM_PRICE}
            <span className="text-base font-semibold tracking-normal"> a month</span>
          </p>
          <p className="text-sm font-semibold">First {TRIAL_DAYS} days free. No card needed to start.</p>
          <Features items={PREMIUM_FEATURES} />
        </section>
      </div>

      <h2>Your free month</h2>
      <ul>
        <li>
          Your {TRIAL_DAYS} days of Premium start when you join FinBoy, the moment you agree to the terms.
          Households that joined before Premium launched get their {TRIAL_DAYS} days from launch day.
        </li>
        <li>
          When the trial ends you move to Free. Nothing is charged unless you choose Premium, and
          your records stay as they are.
        </li>
        <li>
          If you pay during your trial, your paid month starts when the trial ends, so you lose no
          free days.
        </li>
      </ul>

      <h2>Paying</h2>
      <ul>
        <li>
          Pay from Plan in the web app, or from the link FinBoy sends you on WhatsApp. You pay on
          PayU&apos;s secure page by UPI, card or net banking.
        </li>
        <li>
          {PREMIUM_PRICE} is the full price; FinBoy adds no fees. Each payment adds one calendar
          month — for example, 2 December to 2 January.
        </li>
        <li>
          Where PayU offers it, you can turn on UPI AutoPay or card auto-renew while paying, so each
          month renews by itself. You&apos;re told before every renewal charge, and you can turn
          AutoPay off at any time from Plan, your UPI app or your bank.
        </li>
      </ul>

      <h2>How Premium is delivered</h2>
      <p>
        Premium is an online service; nothing is shipped. It switches on as soon as PayU confirms
        your payment — usually within a minute — in the web app and on WhatsApp together. If your
        bank takes longer to confirm, Premium switches on by itself when it does.
      </p>

      <h2>Stopping and refunds</h2>
      <p>
        Stop whenever you like: Premium lasts until the end of the month you paid for. Our{" "}
        <Link href="/refund-policy" className="font-semibold underline underline-offset-4">
          cancellation and refund policy
        </Link>{" "}
        covers refunds and failed payments. Questions? Write to{" "}
        <a href={`mailto:${BUSINESS.email}`} className="font-semibold underline underline-offset-4">
          {BUSINESS.email}
        </a>
        .
      </p>
    </LegalPage>
  );
}
