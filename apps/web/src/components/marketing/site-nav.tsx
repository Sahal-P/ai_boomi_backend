"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Brand } from "@/components/brand";
import { cn } from "@/lib/utils";

const links = [
  { label: "How it works", href: "#how-it-works" },
  { label: "Voice", href: "#voice" },
  { label: "Simulator", href: "#simulator" },
  { label: "Trust", href: "#trust" },
] as const;

export function SiteNav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="fixed inset-x-0 top-0 z-40 px-3 pt-3 sm:px-5">
      <div
        className={cn(
          "mx-auto flex h-16 max-w-[1360px] items-center justify-between rounded-full px-3 transition-[background,box-shadow,border-color,backdrop-filter] duration-500 ease-out-expo sm:px-6",
          scrolled ? "glass bg-white/80" : "border border-transparent",
        )}
      >
        <Brand />
        <nav aria-label="Main navigation" className="hidden items-center gap-9 md:flex">
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
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            className="hidden h-10 items-center rounded-full px-4 text-[13px] font-semibold text-ink/80 transition-colors hover:text-ink sm:inline-flex"
          >
            Open app
          </Link>
          <Link
            href="/sources"
            className="inline-flex h-10 items-center rounded-full bg-white px-5 text-[13px] font-semibold text-ink shadow-[0_1px_2px_rgba(20,16,60,0.06),0_8px_24px_-10px_rgba(76,52,170,0.35)] transition-transform duration-300 ease-out-expo hover:-translate-y-0.5"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}
