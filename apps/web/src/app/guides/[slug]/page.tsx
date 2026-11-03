import type { Metadata } from "next";
import { notFound } from "next/navigation";
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
  return <ContentPage item={item} path={`/guides/${slug}`} guide>{slug === "track-cash-and-upi-expenses" && <section className="space-y-4 pt-4"><h2 className="text-2xl font-semibold">A simple diary for your spreadsheet</h2><p>Download a blank CSV and fill it in using your own spreadsheet. For example, you might note tea for ₹20 paid in cash, or lunch for ₹120 paid by UPI. The template stays wherever you save it. It is not an import file for FinBoy.</p><a className="inline-block underline" href="/expense-diary-template.csv" download>Download the blank expense diary</a></section>}</ContentPage>;
}
