import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ContentPage } from "@/components/marketing/seo-page";
import { features, findContent } from "@/lib/seo/content";
import { publicMetadata } from "@/lib/seo/metadata";

type Props = { params: Promise<{ slug: string }> };
export const dynamicParams = false;
export function generateStaticParams() { return Object.keys(features).map(slug => ({ slug })); }
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const item = findContent(features, slug);
  if (!item) notFound();
  return publicMetadata(`/features/${slug}`, item.title, item.description);
}
export default async function FeaturePage({ params }: Props) {
  const { slug } = await params;
  const item = findContent(features, slug);
  if (!item) notFound();
  return <ContentPage item={item} path={`/features/${slug}`} />;
}
