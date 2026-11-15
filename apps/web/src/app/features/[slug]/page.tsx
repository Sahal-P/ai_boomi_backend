import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ContentPage } from "@/components/marketing/seo-page";
import { ChatPreview } from "@/components/marketing/chat-preview";
import { StartLink } from "@/components/marketing/start-link";
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
  const preview = slug === "whatsapp-expense-tracker" ? (
    <>
      <StartLink className="inline-flex rounded-full bg-ink px-6 py-3 text-base font-semibold text-white" />
      <section aria-labelledby="chat-preview-title" className="rounded-3xl bg-well p-5 sm:p-8">
        <h2 id="chat-preview-title" className="mb-5 text-2xl font-semibold tracking-tight">Try a sample WhatsApp conversation</h2>
        <ChatPreview />
      </section>
    </>
  ) : undefined;
  return <ContentPage item={item} path={`/features/${slug}`} preview={preview} />;
}
