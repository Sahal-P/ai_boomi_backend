import type { Viewport } from "next";

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
      <SiteNav />
      <SceneLayerMount />
      {/* The app's glass field. isolation-auto keeps DOM marked z-20 above the shared 3D layer (z-10). */}
      <main id="main" className="bg-field isolation-auto">
        <Hero />
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
