import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage } from "@/components/legal/legal-page";
import { BUSINESS, PREMIUM_PRICE } from "@/lib/business";

export const metadata: Metadata = {
  title: "Terms",
  description: "The plain-language terms for using FinBoy.",
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms" updated="2 November 2026">
      <p>
        FinBoy helps you track your own money by WhatsApp, voice or the web. It is run by{" "}
        {BUSINESS.name} and is still in beta. FinBoy is free to use, and Premium costs{" "}
        {PREMIUM_PRICE} a month after a free first month. By creating an account or using FinBoy
        you agree to these terms.
      </p>

      <h2>What FinBoy is — and isn&apos;t</h2>
      <ul>
        <li>
          FinBoy shows totals from the records you add, confirm or import. It is not your bank,
          and your actual bank balance may differ.
        </li>
        <li>
          FinBoy explains and models cash flow; it never recommends a fund, stock or other
          investment, and it is not financial, tax or legal advice.
        </li>
        <li>FinBoy never moves money and never asks for bank passwords, PINs or OTPs.</li>
      </ul>

      <h2>Your account</h2>
      <ul>
        <li>One account is for one household. Keep your phone and Google account secure.</li>
        <li>
          Only confirm a WhatsApp sign-in card if you started signing in yourself, just now. Never
          send a code someone else gave you.
        </li>
        <li>You are responsible for checking records before you confirm them.</li>
      </ul>

      <h2>Premium and payments</h2>
      <ul>
        <li>
          Premium adds voice notes and spoken replies, Ask FinBoy, reading photos and screenshots,
          and Google Pay statement import. Everything else stays free. See{" "}
          <Link href="/pricing" className="font-semibold underline underline-offset-4">
            Pricing
          </Link>
          .
        </li>
        <li>
          Every new household gets 30 days of Premium free from the day it joins. When the trial
          ends you move to Free; nothing is charged unless you choose Premium.
        </li>
        <li>
          Premium costs {PREMIUM_PRICE} a month. Each payment adds one calendar month, starting
          when your trial or your current paid month ends.
        </li>
        <li>
          Payments are handled by PayU, our payment partner. FinBoy never sees or keeps your card,
          UPI or bank details.
        </li>
        <li>
          Where PayU offers it, you may turn on AutoPay (UPI AutoPay or card auto-renew) to renew
          each month. You&apos;ll be told before each renewal charge, and you can turn AutoPay off
          at any time from Plan, your UPI app or your bank. If a renewal fails, Premium continues
          for 3 days while FinBoy tries again; then you move to Free.
        </li>
        <li>
          We&apos;ll tell you at least 30 days before a price change, and a new price never applies
          to a month you&apos;ve already paid for.
        </li>
        <li>
          Stopping, refunds and failed payments are covered by our{" "}
          <Link href="/refund-policy" className="font-semibold underline underline-offset-4">
            cancellation and refund policy
          </Link>
          .
        </li>
      </ul>

      <h2>Fair use</h2>
      <p>
        On every plan, each household has a daily limit on voice and AI requests, and the number of
        new accounts is limited. Don&apos;t misuse FinBoy, send it other people&apos;s information,
        or try to reach records that aren&apos;t yours.
      </p>

      <h2>Changes and ending</h2>
      <p>
        FinBoy is a beta: features may change or stop. We&apos;ll tell you on WhatsApp or here before
        any change that affects your data or what you pay for, and if we stop offering Premium
        we&apos;ll refund any month you paid for but can&apos;t use. You can delete your account at
        any time from Privacy &amp; data.
      </p>

      <h2>Contact</h2>
      <p>
        Questions or complaints: write to{" "}
        <a href={`mailto:${BUSINESS.email}`} className="font-semibold underline underline-offset-4">
          {BUSINESS.email}
        </a>{" "}
        or see our{" "}
        <Link href="/contact" className="font-semibold underline underline-offset-4">
          contact page
        </Link>
        .
      </p>
    </LegalPage>
  );
}
