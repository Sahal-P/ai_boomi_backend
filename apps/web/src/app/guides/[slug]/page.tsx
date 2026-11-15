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
export default async function GuidePage({ params }: Props) {
  const { slug } = await params;
  const item = findContent(guides, slug);
  if (!item) notFound();
  return <ContentPage item={item} path={`/guides/${slug}`} guide>{slug === "track-cash-and-upi-expenses" && <section className="space-y-4 pt-4"><h2 className="text-2xl font-semibold">Try a simple cash and UPI diary</h2><p>Use the free browser diary to add purchases, see totals and download a CSV. It does not need an account or send your entries to FinBoy.</p><Link className="inline-block font-semibold underline underline-offset-4" href="/tools/cash-upi-expense-diary">Open the cash and UPI expense diary</Link><p>Prefer a blank sheet? Download the template and fill it in using your own spreadsheet. It is a spreadsheet resource, not a FinBoy import file.</p><a className="inline-block underline" href="/expense-diary-template.csv" download>Download the blank expense diary</a></section>}</ContentPage>;
}
