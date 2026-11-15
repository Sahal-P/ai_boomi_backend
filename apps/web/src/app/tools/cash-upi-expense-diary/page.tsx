import Link from "next/link";
import { CashUpiDiary } from "@/components/marketing/cash-upi-diary";
import { JsonLd, SeoPage } from "@/components/marketing/seo-page";
import { publicMetadata, SITE_URL } from "@/lib/seo/metadata";

const path = "/tools/cash-upi-expense-diary";
export const metadata = publicMetadata(
  path,
  "Free cash and UPI expense diary",
  "Track cash and UPI purchases together in a free browser diary. See totals and download a CSV without signing in.",
);

export default function CashUpiExpenseDiaryPage() {
  return (
    <SeoPage title="Free cash and UPI expense diary">
      <JsonLd value={{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "FinBoy", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Money guides", item: `${SITE_URL}/guides` },
          { "@type": "ListItem", position: 3, name: "Cash and UPI expense diary", item: `${SITE_URL}${path}` },
        ],
      }} />
      <p className="max-w-3xl text-lg text-ink-soft sm:text-xl">
        Add cash and UPI purchases to one simple list, see the totals and download a CSV for your
        spreadsheet. No account is needed.
      </p>
      <CashUpiDiary />
      <section className="space-y-4 pt-3">
        <h2 className="text-2xl font-semibold tracking-tight">How to use the diary</h2>
        <ol className="list-decimal space-y-3 pl-6">
          <li>Add the date, what you bought, the amount, payment method and category.</li>
          <li>Check the Cash, UPI and Total cards. Remove an entry if you added it twice.</li>
          <li>Download the CSV before you leave if you want to keep it. It opens in a spreadsheet.</li>
        </ol>
        <p>
          For example, ₹20 cash tea and a ₹120 UPI lunch add up to ₹140. The totals include only
          what you enter here; this tool does not connect to a bank or automatically read payments.
        </p>
        <p>
          The CSV is a spreadsheet resource, not an import file for FinBoy. For a diary that
          saves your records through WhatsApp and the web, see the{" "}
          <Link href="/features/whatsapp-expense-tracker" className="font-semibold underline underline-offset-4">WhatsApp expense tracker</Link>.
          You can also read our{" "}
          <Link href="/guides/track-cash-and-upi-expenses" className="font-semibold underline underline-offset-4">guide to tracking cash and UPI together</Link>.
        </p>
      </section>
    </SeoPage>
  );
}
