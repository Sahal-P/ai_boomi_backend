import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * Faceted ink gem with a sunflower ₹ — the theme's two accents, reading as "money, refined" at
 * 20–40 px on glass, white and yellow alike. Built from CSS gradients (no SVG ids), so any number
 * of instances render even when one of them sits inside a hidden subtree.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span aria-hidden="true" className={cn("relative inline-grid size-8 shrink-0 place-items-center", className)}>
      <span className="absolute inset-[14%] rotate-45 rounded-[32%] bg-[linear-gradient(200deg,#454a53,#0e1013_58%)] shadow-[0_4px_12px_-4px_rgba(14,16,19,0.55)]" />
      <span className="absolute inset-[14%] rotate-45 rounded-[32%] bg-[linear-gradient(135deg,rgba(255,255,255,0.3),rgba(255,255,255,0)_55%)]" />
      <svg
        viewBox="0 0 24 24"
        className="relative size-[42%]"
        fill="none"
        stroke="#fed234"
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M6 3h12M6 8h12M6 13h3M9 13c6.667 0 6.667-10 0-10M6 13l8.5 8" />
      </svg>
    </span>
  );
}

export function Brand({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} aria-label="FinBoy home" className={cn("inline-flex items-center gap-2", className)}>
      <BrandMark />
      <span className="text-[1.45rem] font-bold tracking-[-0.05em] text-ink">finboy</span>
    </Link>
  );
}
