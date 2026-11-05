import Link from "next/link";
import type { ReactNode } from "react";
import { StartLink, WhatsAppEntryProvider } from "@/components/marketing/start-link";
import { CONTENT_UPDATED_AT, type Content } from "@/lib/seo/content";
import { SITE_URL } from "@/lib/seo/metadata";

export function JsonLd({ value }: { value: Record<string, unknown> }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(value).replace(/</g, "\\u003c") }} />;
}

export function SeoPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main id="main" className="mx-auto min-h-screen max-w-4xl px-6 py-10 text-ink sm:px-10 sm:py-14">
      <nav aria-label="Resources" className="mb-12 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm font-semibold">
        <Link href="/" className="text-lg">FinBoy</Link><Link href="/guides">Money guides</Link><Link href="/pricing">Pricing</Link>
      </nav>
      <h1 className="mb-7 text-[clamp(2rem,6vw,3.25rem)] leading-tight font-bold tracking-tight">{title}</h1>
      <div className="space-y-7 text-base leading-relaxed sm:text-lg">{children}</div>
      <div className="mt-12 flex flex-wrap gap-4">
        <WhatsAppEntryProvider>
          <StartLink className="rounded-full bg-ink px-6 py-3 font-semibold text-white" />
        </WhatsAppEntryProvider>
        <Link className="rounded-full border border-ink px-6 py-3 font-semibold" href="/pricing">See pricing</Link>
      </div>
      <footer className="mt-12 flex flex-wrap gap-5 border-t border-ink/15 pt-6 text-sm"><Link href="/privacy-policy">Privacy Policy</Link><Link href="/terms">Terms</Link><Link href="/contact">Contact</Link></footer>
    </main>
  );
}

export function ContentPage({ item, path, guide = false, children }: { item: Content; path: string; guide?: boolean; children?: ReactNode }) {
  const breadcrumbs = [{ "@type": "ListItem", position: 1, name: "FinBoy", item: SITE_URL }];
  if (guide) breadcrumbs.push({ "@type": "ListItem", position: 2, name: "Money guides", item: `${SITE_URL}/guides` });
  breadcrumbs.push({ "@type": "ListItem", position: breadcrumbs.length + 1, name: item.title, item: `${SITE_URL}${path}` });
  return <SeoPage title={item.title}>
    <JsonLd value={{ "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: breadcrumbs }} />
    {guide && <JsonLd value={{ "@context": "https://schema.org", "@type": "Article", headline: item.title, description: item.description, datePublished: CONTENT_UPDATED_AT, dateModified: CONTENT_UPDATED_AT, author: { "@type": "Organization", name: "FinBoy", url: SITE_URL }, publisher: { "@type": "Organization", name: "FinBoy", url: SITE_URL }, mainEntityOfPage: `${SITE_URL}${path}` }} />}
    <p className="max-w-3xl text-lg text-ink-soft sm:text-xl">{item.intro}</p>
    <p className="text-sm text-ink-soft">{guide ? "By the FinBoy team · " : ""}Reviewed <time dateTime={CONTENT_UPDATED_AT}>4 November 2026</time></p>
    {item.sections.map(section => <section key={section.heading} className="space-y-4 pt-4">
      <h2 className="text-2xl leading-snug font-semibold tracking-tight">{section.heading}</h2>
      {section.paragraphs.map(paragraph => <p key={paragraph}>{paragraph}</p>)}
      {section.steps && <ol className="list-decimal space-y-3 pl-6">{section.steps.map(step => <li key={step}>{step}</li>)}</ol>}
    </section>)}
    {item.source && <p className="text-base"><a className="font-semibold underline underline-offset-4" href={item.source.href}>{item.source.label}</a></p>}
    {children}
    <aside className="rounded-2xl border border-ink/10 bg-white/60 p-6"><h2 className="mb-4 text-xl font-semibold">Keep exploring</h2><ul className="space-y-3">{item.related.map(link => <li key={link.href}><Link className="font-semibold underline underline-offset-4" href={link.href}>{link.label}</Link></li>)}</ul></aside>
  </SeoPage>;
}
