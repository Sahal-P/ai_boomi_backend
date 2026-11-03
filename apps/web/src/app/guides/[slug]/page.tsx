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
  return <ContentPage item={item} path={`/guides/${slug}`} guide />;
}
