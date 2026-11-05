import type { Metadata } from "next";
import { LegalPage } from "@/components/legal/legal-page";
import { BUSINESS } from "@/lib/business";

export const metadata: Metadata = {
  robots: { index: true, follow: true },
  alternates: { canonical: "/contact" },
  title: "Contact",
  description: "How to reach FinBoy about your account, a payment or your data.",
};

export default function ContactPage() {
  const dial = BUSINESS.phone?.replace(/[^\d+]/g, "") ?? "";
  const email = (
    <a href={`mailto:${BUSINESS.email}`} className="font-semibold underline underline-offset-4">
      {BUSINESS.email}
    </a>
  );
  return (
    <LegalPage title="Contact" updated="2 November 2026">
      <p>
        {BUSINESS.name ? `FinBoy is run by ${BUSINESS.name}. ` : null}We&apos;re glad to help with
        your account, a payment or your data, and we aim to reply within two working days.
      </p>

      <dl className="mt-6 grid gap-x-6 gap-y-3 rounded-3xl bg-well p-5 ring-1 ring-ink/5 sm:grid-cols-[7rem_1fr]">
        <dt className="font-semibold">Email</dt>
        <dd className="break-all">{email}</dd>
        {BUSINESS.phone ? (
          <>
            <dt className="font-semibold">Phone</dt>
            <dd>
              {dial.length >= 10 ? (
                <a href={`tel:${dial}`} className="font-semibold underline underline-offset-4">
                  {BUSINESS.phone}
                </a>
              ) : (
                BUSINESS.phone
              )}
            </dd>
          </>
        ) : null}
        {BUSINESS.address ? (
          <>
            <dt className="font-semibold">Address</dt>
            <dd>{BUSINESS.address}</dd>
          </>
        ) : null}
      </dl>

      <h2>About a payment</h2>
      <p>
        Tell us the date and amount, and PayU&apos;s reference if you have it. Never send your card
        number, UPI PIN, OTP or bank password: FinBoy will never ask for them.
      </p>

      <h2>About your data</h2>
      <p>
        To ask what we hold, correct it or have it erased, write to {email}
        {BUSINESS.grievanceOfficer ? ` for our grievance officer, ${BUSINESS.grievanceOfficer}` : null}. You
        can also export or delete everything yourself from Privacy &amp; data in the app.
      </p>
    </LegalPage>
  );
}
