import type { Viewport } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/marketing/seo-page";
import { features } from "@/lib/seo/content";
import { publicMetadata, SITE_URL, SITE_TITLE, SITE_DESCRIPTION } from "@/lib/seo/metadata";

import { FinalCta, SiteFooter } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { ProductMosaic } from "@/components/marketing/product-mosaic";
import { SimulatorSection } from "@/components/marketing/simulator-section";
import { SiteNav } from "@/components/marketing/site-nav";
import { SourcesMarquee } from "@/components/marketing/sources-marquee";
import { TrustSection } from "@/components/marketing/trust-section";
import { VoiceSection } from "@/components/marketing/voice-section";
import { SmoothScroll } from "@/components/motion/smooth-scroll";
import { SceneLayerMount } from "@/components/three/scene-slot";

// The page opens on the yellow hero.
export const metadata = {
  ...publicMetadata("/", SITE_TITLE, SITE_DESCRIPTION),
  ...(process.env.GOOGLE_SITE_VERIFICATION ? { verification: { google: process.env.GOOGLE_SITE_VERIFICATION } } : {}),
};
export const viewport: Viewport = { themeColor: "#fed234" };

export default function Home() {
  return (
    <SmoothScroll>
      <a
        href="#main"
        className="sr-only rounded-full bg-ink px-4 py-3 text-white focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50"
      >
        Skip to content
      </a>
      <JsonLd value={{ "@context": "https://schema.org", "@graph": [
        { "@type": "Organization", "@id": `${SITE_URL}/#organization`, name: "FinBoy", url: SITE_URL, logo: `${SITE_URL}/brand/finboy-icon-512.png` },
        { "@type": "WebSite", "@id": `${SITE_URL}/#website`, name: "FinBoy", url: SITE_URL, publisher: { "@id": `${SITE_URL}/#organization` } },
      ] }} />
      <SiteNav />
      <SceneLayerMount />
      {/* The app's glass field. isolation-auto keeps DOM marked z-20 above the shared 3D layer (z-10). */}
      <main id="main" className="bg-field isolation-auto">
        <Hero />
        <section aria-label="Explore FinBoy" className="mx-auto max-w-[1360px] px-6 py-12 sm:px-10 lg:px-16">
          <h2 className="mb-6 text-2xl font-semibold text-ink">Track spending your way</h2>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(features).map(([slug, item]) => <li key={slug}><Link className="surface block h-full rounded-2xl p-5 text-sm font-semibold text-ink underline-offset-4 hover:underline" href={`/features/${slug}`}>{item.title}</Link></li>)}</ul>
          <p className="mt-6 text-sm text-ink-soft">Gmail import is restricted and invite-only. <Link className="font-semibold underline" href="/guides">Read the money guides</Link> for practical ways to get started.</p>
        </section>
        <SourcesMarquee />
        <HowItWorks />
        <VoiceSection />
        <SimulatorSection />
        <ProductMosaic />
        <TrustSection />
        <FinalCta />
      </main>
      <SiteFooter />
    </SmoothScroll>
  );
}
