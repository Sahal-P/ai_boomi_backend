"use client";

import { useEffect, useMemo, useRef, type ReactNode } from "react";

import { mergeRefs } from "@/components/liquid-glass/merge-refs";
import { useLiquidGlass } from "@/components/liquid-glass/use-liquid-glass";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

/**
 * A page's actions. Phones and tablets keep them in the header's flow; on desktop they float in a
 * Liquid Glass toolbar capsule at the top right that the page scrolls beneath (liquid-glass.css,
 * `.page-actions`). Its width goes to `--page-actions-width` on the page's `main`, so the title
 * and the offline banner keep clear of it.
 */
export function PageActions({ children }: { children: ReactNode }) {
  const desktop = useMediaQuery("(min-width: 64rem)");
  // Destructured: the React Compiler treats an object whose member is passed as `ref` as a ref.
  const { attach, filter } = useLiquidGlass<HTMLDivElement>({ bezel: 14, thickness: 16, enabled: desktop });
  const capsule = useRef<HTMLDivElement | null>(null);
  const attachCapsule = useMemo(() => mergeRefs(attach, capsule), [attach]);

  useEffect(() => {
    const element = capsule.current;
    const host = element?.closest("main") ?? element?.parentElement;
    if (!desktop || !element || !host) return;
    const observer = new ResizeObserver(() => host.style.setProperty("--page-actions-width", `${element.offsetWidth}px`));
    observer.observe(element);
    return () => {
      observer.disconnect();
      host.style.removeProperty("--page-actions-width");
    };
  }, [desktop]);

  return (
    <div
      ref={attachCapsule}
      data-scroll-edge={desktop ? "top" : undefined}
      className={cn("page-actions flex flex-wrap items-center gap-2 max-sm:w-full", desktop && "lg")}
    >
      {filter}
      {children}
    </div>
  );
}
