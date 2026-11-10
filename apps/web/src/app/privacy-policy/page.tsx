import type { Metadata } from "next";
import { LegalPage } from "@/components/legal/legal-page";
import { BUSINESS } from "@/lib/business";

export const metadata: Metadata = {
  robots: { index: true, follow: true },
  alternates: { canonical: "/privacy-policy" },
  title: "Privacy Policy",
  description: "What FinBoy keeps, what it never keeps, who processes it, and how to delete it.",
};

export default function PrivacyPolicyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="7 November 2026">
      <p>
        FinBoy helps you keep track of your own money: what came in, what went out and what is due.
        This page says exactly what we keep, what we never keep, and how to delete everything.
      </p>

      <h2>What we keep</h2>
      <ul>
        <li>
          Your money records: the amount, date, money in or out, who you paid or who paid you, the
          category, and any dues you add. Nothing counts until you confirm it.
        </li>
        <li>
          How you sign in: an encrypted copy of your WhatsApp number (shown to you masked, and used
          only for messages you ask for, like a place opening up, a reminder or the coach&apos;s nudges), or a one-way code that identifies your Google account plus a
          masked email like &ldquo;s***@***.com&rdquo;. We don&apos;t keep your name or photo.
        </li>
        <li>
          Your chats with FinBoy, typed or spoken: the words of each question (a voice question is
          kept as its text, never as audio) and FinBoy&apos;s answer, so you can pick up where you
          left off on the website or WhatsApp. If you turn on the coach&apos;s WhatsApp messages,
          each one FinBoy sends is kept in the same chat.
        </li>
        <li>
          What FinBoy remembers about you to give more personal answers, like your goals, who
          people are to you or how your income comes, including a lasting fact a diary message
          states, like who your milkman is (the fact only, never the message). With each memory and
          chat summary we may keep a list of numbers that helps FinBoy find the right ones; it is
          deleted with them. You can see, edit or delete each memory, or turn memory off, on the
          Memory page.
        </li>
        <li>
          Records of your choices (confirm, change, undo), consent and reminder settings, daily
          usage counts, and a short history of account events. These never contain amounts,
          names or messages.
        </li>
        <li>
          If you connect Gmail: read-only access, an encrypted access token, and short snippets
          (at most 80 characters per field) that show where a figure came from.
        </li>
        <li>
          If you pay for Premium: an encrypted copy of the email address and phone number PayU
          needs for your receipt (with WhatsApp, we use the number you sign in with), your plan
          dates, and a record of each payment — the amount, the dates it covers, its status, the
          kind of payment (like UPI or card, never the number) and PayU&apos;s reference.
        </li>
      </ul>

      <h2>What we never keep</h2>
      <ul>
        <li>
          Your voice notes, photos or screenshots. Diary messages like &ldquo;chai 20&rdquo; are
          kept only as the record you save, not as messages.
        </li>
        <li>What you type or say to quick add — only the record you save.</li>
        <li>Full emails, login codes, Google sign-in tokens or passwords.</li>
        <li>Card numbers, UPI IDs, bank account details, PINs or OTPs. These stay with PayU and your bank.</li>
      </ul>

      <h2>Who helps us process it</h2>
      <p>
        To understand what you say or send, FinBoy uses these services, only for that request and
        without letting them keep or train on your data where they offer that choice: OpenAI
        (reading text, screenshots and speech, answering your questions with the figures from your
        records, the memories and the recent chat that each answer needs, and turning memories, chat
        summaries and searches into numbers that help find the right ones), Liquid AI (quickly telling what a message, question
        or photo is about, so common ones are answered sooner), Sarvam AI (speech in English, Hindi
        and Malayalam, and spoken Malayalam replies), Groq (speech in English and Hindi), Resemble
        and Google Gemini (spoken replies), Meta (delivering WhatsApp messages) and Google (sign-in
        and, if you connect it, Gmail). If you pay for Premium, PayU processes the payment and
        receives your email address and phone number for the receipt. FinBoy never sells your data
        and never shows ads.
      </p>

      <h2>What FinBoy&apos;s team can see</h2>
      <p>
        The few people who run FinBoy can see account activity, to keep the service working and to
        help you: when you joined and last used FinBoy, your plan and Premium payments, daily usage
        counts, whether messages were delivered, and whether WhatsApp or Google is linked. They
        never see your records, amounts, who you paid, your messages, your chats with FinBoy, what
        it remembers about you or your phone number. They can
        pause or erase an account, for example when you ask, and every such step is recorded.
      </p>

      <h2>How long we keep it</h2>
      <p>
        As long as you have an account. A WhatsApp sign-up that never says yes is forgotten after
        seven days. Private server backups are kept for seven days and then overwritten. When you
        delete your account, payment records stay as FinBoy&apos;s sales records, as tax and
        accounting law requires, without your email address or phone number.
      </p>

      <h2>Your choices</h2>
      <ul>
        <li>Export your records, chats and memories any time from Privacy &amp; data.</li>
        <li>
          On the Memory page, edit or delete what FinBoy remembers, turn memory off, or clear your
          chat history. On WhatsApp, send &ldquo;memory off&rdquo;, &ldquo;forget everything&rdquo;
          or &ldquo;clear chat history&rdquo;.
        </li>
        <li>
          The coach&apos;s WhatsApp messages come only if you ask for them, at most one a day: send
          &ldquo;coach on&rdquo; or &ldquo;coach off&rdquo;.
        </li>
        <li>Send STOP on WhatsApp to stop all messages; send START to turn them back on.</li>
        <li>
          Delete your account from Privacy &amp; data → Delete my account. Your records, dues,
          chats, memories, sign-ins, Gmail access, receipt contact details and AutoPay go at once; only a count of
          account events and your payment records remain.
        </li>
      </ul>

      <h2>Contact and grievances</h2>
      <p>
        {BUSINESS.name ? `FinBoy is run by ${BUSINESS.name}. ` : null}Under India&apos;s Digital
        Personal Data Protection Act you can ask what we hold, correct it, or have it erased. Write
        to{" "}
        {BUSINESS.grievanceOfficer ? `our grievance officer, ${BUSINESS.grievanceOfficer}, at ` : "us at "}
        <a href={`mailto:${BUSINESS.email}`} className="font-semibold underline underline-offset-4">
          {BUSINESS.email}
        </a>
        .
      </p>
    </LegalPage>
  );
}
