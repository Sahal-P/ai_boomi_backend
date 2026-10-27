import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { BrandMark } from "@/components/brand";
import { Reveal } from "@/components/motion/reveal";
import { SceneSlot } from "@/components/three/scene-slot";

export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="px-3 pb-6 sm:px-5">
      <div className="surface relative mx-auto max-w-[1400px] overflow-hidden rounded-[2.5rem] bg-[radial-gradient(60rem_30rem_at_50%_0%,rgb(255_255_255/0.85),transparent_75%)]">
        <SceneSlot spec={{ name: "ribbon" }} className="absolute inset-x-0 bottom-0 h-[52%]" />
        <div className="relative z-20 px-6 pt-20 pb-[min(60vw,22rem)] text-center sm:px-10 sm:pt-24">
          <Reveal>
            <p className="eyebrow text-ink-soft">Start in two minutes</p>
            <h2 id="cta-title" className="mx-auto mt-4 max-w-3xl text-[clamp(2.3rem,5vw,4.4rem)] leading-[1.03] font-semibold tracking-[-0.045em] text-ink">
              Your money already leaves a trail. Let’s make it useful.
            </h2>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link
                href="/login"
                className="group inline-flex h-12 items-center gap-3 rounded-full bg-ink pr-2 pl-6 text-sm font-semibold text-white shadow-lift transition-transform duration-300 ease-out-expo hover:-translate-y-0.5"
              >
                Get started free
                <span className="grid size-8 place-items-center rounded-full bg-white/15 transition-transform group-hover:translate-x-0.5">
                  <ArrowRight className="size-4" aria-hidden="true" />
                </span>
              </Link>
              <Link href="/demo" className="glass inline-flex h-12 items-center rounded-full px-6 text-sm font-semibold text-ink">
                Explore sample data
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
    <footer className="mx-auto flex max-w-[1360px] flex-col gap-6 px-6 py-12 text-sm text-ink-soft sm:px-10 md:flex-row md:items-center md:justify-between lg:px-16">
      <div className="flex items-center gap-3">
        <BrandMark className="size-7" />
        <p>© {new Date().getFullYear()} FinBoy. Made in Kerala.</p>
      </div>
      <p className="max-w-md text-xs leading-relaxed text-ink-subtle">
        Figures are estimates from email-derived and confirmed records. Your actual bank balance may differ.
        FinBoy is not an investment adviser.
      </p>
      <nav aria-label="Legal" className="flex gap-4 text-xs font-semibold">
        <Link href="/privacy-policy" className="hover:text-ink">
          Privacy Policy
        </Link>
        <Link href="/terms" className="hover:text-ink">
          Terms
        </Link>
      </nav>
    </footer>
  );
}
