import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage } from "@/components/legal/legal-page";
import { BUSINESS, PREMIUM_PRICE } from "@/lib/business";

export const metadata: Metadata = {
  robots: { index: true, follow: true },
  alternates: { canonical: "/refund-policy" },
  title: "Cancellation and refund policy",
  description: "How to stop FinBoy Premium, and when money paid for it comes back.",
};

export default function RefundPolicyPage() {
  const email = (
    <a href={`mailto:${BUSINESS.email}`} className="font-semibold underline underline-offset-4">
      {BUSINESS.email}
    </a>
  );
  return (
    <LegalPage title="Cancellation and refund policy" updated="2 November 2026">
      <p>
        FinBoy Premium costs {PREMIUM_PRICE} a month and is paid one month at a time (see{" "}
        <Link href="/pricing" className="font-semibold underline underline-offset-4">
          Pricing
        </Link>
        ). This page explains how to stop it and when money comes back.
      </p>

      <h2>Cancelling</h2>
      <ul>
        <li>
          Paying month by month, there&apos;s nothing to cancel. If you don&apos;t pay again,
          Premium ends with the month you paid for and you move to Free. Your records stay.
        </li>
        <li>
          With AutoPay on, turn it off in the app (Plan → Turn off AutoPay) or from your UPI app or
          bank. No further charges are made, and Premium lasts until the end of the month you
          paid for.
        </li>
        <li>Deleting your account also turns AutoPay off.</li>
      </ul>

      <h2>Refunds</h2>
      <ul>
        <li>
          A month you&apos;ve paid for isn&apos;t refunded, in full or in part, when you stop
          Premium or delete your account partway through it.
        </li>
        <li>
          If you were charged by mistake — twice for the same month, or after you turned AutoPay
          off — write to {email} and we&apos;ll refund that payment in full.
        </li>
        <li>If we stop offering Premium, we&apos;ll refund any month you paid for but can&apos;t use.</li>
        <li>
          Refunds go back to the way you paid, through PayU, and usually reach you within 5–7
          working days of being issued.
        </li>
      </ul>

      <h2>Failed or pending payments</h2>
      <ul>
        <li>
          If a payment fails but money left your account, your bank returns it automatically,
          usually within 5–7 working days. You don&apos;t need to do anything.
        </li>
        <li>
          If a payment says &ldquo;Confirming with your bank&rdquo;, Premium switches on by itself
          once your bank confirms. If it still hasn&apos;t after a day, write to us.
        </li>
        <li>
          If an AutoPay renewal doesn&apos;t go through, Premium continues for 3 days while FinBoy
          tries again. After that AutoPay stops and you move to Free; you can pay again at any
          time.
        </li>
      </ul>

      <h2>Asking for a refund</h2>
      <p>
        Write to {email} with the date and amount of the payment. Never send your card number, UPI
        PIN, OTP or bank password: FinBoy will never ask for them. Our{" "}
        <Link href="/contact" className="font-semibold underline underline-offset-4">
          contact page
        </Link>{" "}
        has our other details.
      </p>
    </LegalPage>
  );
}
