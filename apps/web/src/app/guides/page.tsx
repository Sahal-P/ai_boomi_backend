import { publicMetadata } from "@/lib/seo/metadata";
import Link from "next/link";
import { SeoPage } from "@/components/marketing/seo-page";
import { features, guides } from "@/lib/seo/content";

export const metadata = publicMetadata("/guides", "Money guides", "Practical guides to tracking spending and household budgets in India.");
export default function GuidesPage() { return <SeoPage title="Money guides"><p>Practical ways to understand your everyday spending.</p><ul className="space-y-4">{Object.entries(guides).map(([slug, item]) => <li key={slug}><Link className="underline" href={`/guides/${slug}`}>{item.title}</Link></li>)}</ul><h2 className="pt-6 text-2xl font-semibold">Explore FinBoy</h2><ul className="space-y-4">{Object.entries(features).map(([slug, item]) => <li key={slug}><Link className="underline" href={`/features/${slug}`}>{item.title}</Link></li>)}</ul></SeoPage>; }
