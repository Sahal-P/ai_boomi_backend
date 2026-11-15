import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ContentPage } from "@/components/marketing/seo-page";
import { guides, findContent } from "@/lib/seo/content";
import { publicMetadata } from "@/lib/seo/metadata";

type Props = { params: Promise<{ slug: string }> };
export const dynamicParams = false;
export function generateStaticParams() { return Object.keys(guides).map(slug => ({ slug })); }
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const item = findContent(guides, slug);
  if (!item) notFound();
  return publicMetadata(`/guides/${slug}`, item.title, item.description);
}

const planSnapshot = [
  { name: "FinBoy", href: "/pricing", plan: "Free text entries; 30-day Premium trial. Premium is ₹299/month if you choose to continue." },
  { name: "Expensebit", href: "https://expensebit.com/pricing", plan: "Free during beta. Its page says early users keep their current access free; Plus is planned for later." },
  { name: "Spendzbot", href: "https://spendzbot.com/faq", plan: "Its FAQ says WhatsApp tracking and the dashboard are free while the product grows." },
  { name: "Xpensy", href: "https://xpensy.in/", plan: "The free plan lists WhatsApp tracking at 30/month. New accounts get a 60-day Premium trial; Premium is ₹99/month." },
  { name: "MuneemJi", href: "https://muneemji.app/expense-tracker-on-whatsapp", plan: "Its WhatsApp page describes paid plans. Check the current offer and what it includes." },
] as const;

function PlanSnapshot() {
  return <section aria-labelledby="plan-snapshot" className="space-y-4 rounded-2xl border border-ink/10 bg-white/60 p-5 sm:p-6">
    <h2 id="plan-snapshot" className="text-2xl font-semibold tracking-tight">A quick look at plans</h2>
    <p className="text-sm text-ink-soft">These are the providers’ public descriptions checked on 15 November 2026, not hands-on tests. Prices and limits can change; follow each link for current terms.</p>
    <table className="w-full border-collapse text-left text-sm leading-relaxed">
      <thead><tr><th scope="col" className="border-b border-ink/15 py-3 pr-3">Product and source</th><th scope="col" className="border-b border-ink/15 py-3">Plan snapshot</th></tr></thead>
      <tbody>{planSnapshot.map((item) => <tr key={item.name}><th scope="row" className="w-1/4 border-b border-ink/10 py-3 pr-3 align-top font-semibold"><a className="underline underline-offset-4" href={item.href}>{item.name}</a></th><td className="border-b border-ink/10 py-3 align-top">{item.plan}</td></tr>)}</tbody>
    </table>
  </section>;
}

export default async function GuidePage({ params }: Props) {
  const { slug } = await params;
  const item = findContent(guides, slug);
  if (!item) notFound();
  return <ContentPage item={item} path={`/guides/${slug}`} guide preview={slug === "choose-whatsapp-expense-tracker-india" ? <PlanSnapshot /> : undefined}>{slug === "track-cash-and-upi-expenses" && <section className="space-y-4 pt-4"><h2 className="text-2xl font-semibold">Try a simple cash and UPI diary</h2><p>Use the free browser diary to add purchases, see totals and download a CSV. It does not need an account or send your entries to FinBoy.</p><Link className="inline-block font-semibold underline underline-offset-4" href="/tools/cash-upi-expense-diary">Open the cash and UPI expense diary</Link><p>Prefer a blank sheet? Download the template and fill it in using your own spreadsheet. It is a spreadsheet resource, not a FinBoy import file.</p><a className="inline-block underline" href="/expense-diary-template.csv" download>Download the blank expense diary</a></section>}</ContentPage>;
}
