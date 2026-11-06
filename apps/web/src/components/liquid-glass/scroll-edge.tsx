"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

/** True once the page has scrolled past `threshold` px (passive listener, rAF-free). */
export function useScrolled(threshold = 4) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [threshold]);
  return scrolled;
}

/**
 * Apple's scroll edge effect: content dissolves into the field under floating glass, so the glass
 * can stay clear while its labels keep their contrast. `top` is iOS 27's uniform bar (shown once
 * something scrolls beneath it); `bottom` sits under the phone tab bar. Decorative and inert.
 */
export function ScrollEdge({ top, bottom = false, className }: { top: boolean; bottom?: boolean; className?: string }) {
  return (
    <div
      aria-hidden="true"
      data-top={top ? "on" : "off"}
      data-bottom={bottom ? "on" : "off"}
      className={cn("scroll-edge", className)}
    />
  );
}
