import type { Metadata } from "next";
import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = {
  title: "Terms",
  description: "The plain-language terms for using FinBoy.",
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms" updated="27 October 2026">
      <p>
        FinBoy is a free beta that helps you track your own money by WhatsApp, voice or the web. By
        creating an account or using FinBoy you agree to these terms.
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

      <h2>Fair use</h2>
      <p>
        To keep FinBoy free during the beta, each household has a daily limit on voice and AI
        requests, and the number of new accounts is limited. Don&apos;t misuse FinBoy, send it other
        people&apos;s information, or try to reach records that aren&apos;t yours.
      </p>

      <h2>Changes and ending</h2>
      <p>
        FinBoy is a beta: features may change or stop. We&apos;ll tell you on WhatsApp or here before
        any change that affects your data. You can delete your account at any time from Privacy
        &amp; data.
      </p>

      <h2>Contact</h2>
      <p>Questions or complaints: [contact to be added before sign-up opens].</p>
    </LegalPage>
  );
}
