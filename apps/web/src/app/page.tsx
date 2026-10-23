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
      <main id="main" className="bg-aurora">
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
