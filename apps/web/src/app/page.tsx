import type { Viewport } from "next";
import { JsonLd } from "@/components/marketing/seo-page";
import { publicMetadata, SITE_URL, SITE_TITLE, SITE_DESCRIPTION } from "@/lib/seo/metadata";

import { CorrectionsSection } from "@/components/marketing/corrections-section";
import { FaqSection } from "@/components/marketing/faq-section";
import { FinalCta, SiteFooter } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { PlansSection } from "@/components/marketing/plans-section";
import { ProductMosaic } from "@/components/marketing/product-mosaic";
import { SiteNav } from "@/components/marketing/site-nav";
import { WhatsAppEntryProvider } from "@/components/marketing/start-link";
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

/**
 * WhatsApp first: what happens after "Hi", how mistakes are fixed, what is free and what is
 * Premium, and what FinBoy keeps — each stated from the round contracts and the Privacy Policy.
 */
export default function Home() {
  return (
    <SmoothScroll>
      <WhatsAppEntryProvider>
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
          <HowItWorks />
          <CorrectionsSection />
          <VoiceSection />
          <PlansSection />
          <TrustSection />
          <ProductMosaic />
          <FaqSection />
          <FinalCta />
        </main>
        <SiteFooter />
      </WhatsAppEntryProvider>
    </SmoothScroll>
  );
}
