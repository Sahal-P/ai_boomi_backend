"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Brand } from "@/components/brand";
import { ScrollEdge } from "@/components/liquid-glass/scroll-edge";
import { useLiquidGlass } from "@/components/liquid-glass/use-liquid-glass";
import { StartLink } from "@/components/marketing/start-link";
import { cn } from "@/lib/utils";

const links = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Privacy", href: "#privacy" },
  { label: "Pricing", href: "#plans" },
  { label: "FAQ", href: "#faq" },
  { label: "Guides", href: "/guides" },
] as const;

export function SiteNav() {
  const [scrolled, setScrolled] = useState(false);
  // Refracting Liquid Glass once the hero has gone; its lensing materializes as it leaves.
  const { attach, filter } = useLiquidGlass<HTMLDivElement>({ bezel: 16, thickness: 18, enabled: scrolled });

  useEffect(() => {
    // Frosted glass only once the yellow hero has scrolled away: blurred yellow turns muddy.
    const hero = document.querySelector("[data-hero]");
    const onScroll = () => setScrolled(hero ? hero.getBoundingClientRect().bottom <= 72 : window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      {/* Content dissolves under the nav once it floats over the page (Apple's scroll edge). A
          sibling, so it stays beneath the header's stacking context. */}
      <ScrollEdge top={scrolled} />
      <header className="fixed inset-x-0 top-0 z-40 px-3 pt-3 sm:px-5">
        {filter}
        <div
          ref={attach}
          data-scroll-edge="top"
          className={cn(
            "mx-auto flex h-16 max-w-[1360px] items-center justify-between rounded-full px-3 transition-[background-color,box-shadow] duration-500 ease-out-expo sm:px-6",
            // Over the hero: clear glass on the yellow (no blur); phones fill it with sunflower so
            // the drawing never shows through the logo.
            scrolled ? "lg" : "lg-on-color bg-white/25 max-md:bg-sunflower",
          )}
        >
          <Brand />
          <nav aria-label="Main navigation" className="hidden items-center gap-8 md:flex">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-[13px] font-semibold text-ink/80 transition-colors hover:text-ink"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-1 sm:gap-2">
            <Link
              href="/dashboard"
              className="inline-flex h-10 items-center rounded-full px-3 text-[13px] font-semibold whitespace-nowrap text-ink/80 transition-colors hover:text-ink sm:px-4"
            >
              Sign in
            </Link>
            <StartLink
              short
              className="lg-prominent inline-flex h-10 items-center rounded-full px-4 text-[13px] font-semibold whitespace-nowrap hover:-translate-y-0.5 sm:px-5"
            />
          </div>
        </div>
      </header>
    </>
  );
}
