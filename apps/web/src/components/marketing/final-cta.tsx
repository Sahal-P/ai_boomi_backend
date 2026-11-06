import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { BrandMark } from "@/components/brand";
import { StartLink } from "@/components/marketing/start-link";
import { Reveal } from "@/components/motion/reveal";
import { SceneSlot } from "@/components/three/scene-slot";
import { features } from "@/lib/seo/content";

export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="px-3 pb-6 sm:px-5">
      <div className="surface relative mx-auto max-w-[1400px] overflow-hidden rounded-[2.5rem] bg-[radial-gradient(60rem_30rem_at_50%_0%,rgb(255_255_255/0.85),transparent_75%)]">
        <SceneSlot spec={{ name: "ribbon" }} className="absolute inset-x-0 bottom-0 h-[52%]" />
        <div className="relative z-20 px-6 pt-20 pb-[min(60vw,22rem)] text-center sm:px-10 sm:pt-24">
          <Reveal>
            <p className="eyebrow text-ink-soft">Start with one message</p>
            <h2 id="cta-title" className="mx-auto mt-4 max-w-3xl text-[clamp(2.3rem,5vw,4.4rem)] leading-[1.03] font-semibold tracking-[-0.045em] text-balance text-ink">
              Say hi. Then tell FinBoy what you spent today.
            </h2>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <StartLink
                className="group lg-prominent inline-flex h-12 items-center gap-3 rounded-full pr-2 pl-6 text-sm font-semibold hover:-translate-y-0.5"
                after={
                  <span className="grid size-8 place-items-center rounded-full bg-white/15 transition-transform group-hover:translate-x-0.5">
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </span>
                }
              />
              <Link href="/demo" className="lg-static inline-flex h-12 items-center rounded-full px-6 text-sm font-semibold text-ink hover:-translate-y-0.5">
                See a sample account
              </Link>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

export function SiteFooter() {
  return (
    <footer className="mx-auto grid max-w-[1360px] gap-8 px-6 py-12 text-sm text-ink-soft sm:px-10 md:grid-cols-[1fr_auto] md:items-start lg:px-16">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <BrandMark className="size-7" />
          <p>© {new Date().getFullYear()} FinBoy. Made in Kerala.</p>
        </div>
        <p className="max-w-md text-xs leading-relaxed text-ink-subtle">
          Figures are estimates from your recorded entries and imports. Your actual bank balance may differ.
          FinBoy is not an investment adviser.
        </p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2 md:gap-12">
        <nav aria-label="Features" className="flex flex-col gap-2 text-xs font-semibold">
          {Object.entries(features).map(([slug, item]) => (
            <Link key={slug} href={`/features/${slug}`} className="hover:text-ink">
              {item.title}
            </Link>
          ))}
          <Link href="/guides" className="hover:text-ink">
            Money guides
          </Link>
        </nav>
        <nav aria-label="Legal" className="flex flex-col gap-2 text-xs font-semibold">
          <Link href="/about" className="hover:text-ink">About</Link>
          <Link href="/press" className="hover:text-ink">Press</Link>
          <Link href="/pricing" className="hover:text-ink">
            Pricing
          </Link>
          <Link href="/privacy-policy" className="hover:text-ink">
            Privacy Policy
          </Link>
          <Link href="/terms" className="hover:text-ink">
            Terms
          </Link>
          <Link href="/refund-policy" className="hover:text-ink">
            Refunds
          </Link>
          <Link href="/contact" className="hover:text-ink">
            Contact
          </Link>
        </nav>
      </div>
    </footer>
  );
}
