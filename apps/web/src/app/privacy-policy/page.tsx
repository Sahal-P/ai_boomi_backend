import type { Metadata } from "next";
import { LegalPage } from "@/components/legal/legal-page";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What FinBoy keeps, what it never keeps, who processes it, and how to delete it.",
};

export default function PrivacyPolicyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="27 October 2026">
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
          only for messages you ask for, like a place opening up or a reminder), or a one-way code that identifies your Google account plus a
          masked email like &ldquo;s***@***.com&rdquo;. We don&apos;t keep your name or photo.
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
      </ul>

      <h2>What we never keep</h2>
      <ul>
        <li>Your WhatsApp messages, voice notes, photos or screenshots, or their transcripts.</li>
        <li>What you type or say to quick add — only the record you save.</li>
        <li>Full emails, login codes, Google sign-in tokens or passwords.</li>
      </ul>

      <h2>Who helps us process it</h2>
      <p>
        To understand what you say or send, FinBoy uses these services, only for that request and
        without letting them keep or train on your data where they offer that choice: OpenAI
        (reading text, screenshots and speech), Sarvam AI (speech in English, Hindi and Malayalam,
        and spoken Malayalam replies), Groq (speech in English and Hindi), Resemble and Google
        Gemini (spoken replies), Meta (delivering WhatsApp messages) and Google (sign-in and, if
        you connect it, Gmail). FinBoy never sells your data and never shows ads.
      </p>

      <h2>How long we keep it</h2>
      <p>
        As long as you have an account. A WhatsApp sign-up that never says yes is forgotten after
        seven days. Private server backups are kept for seven days and then overwritten.
      </p>

      <h2>Your choices</h2>
      <ul>
        <li>Export your records any time from Privacy &amp; data.</li>
        <li>Send STOP on WhatsApp to stop all messages; send START to turn them back on.</li>
        <li>
          Delete your account from Privacy &amp; data → Delete my account. Your records, dues,
          sign-ins and Gmail access go at once; only a count of account events remains.
        </li>
      </ul>

      <h2>Contact and grievances</h2>
      <p>
        Under India&apos;s Digital Personal Data Protection Act you can ask what we hold, correct
        it, or have it erased. Contact our grievance officer: [name and email to be added before
        sign-up opens].
      </p>
    </LegalPage>
  );
}
