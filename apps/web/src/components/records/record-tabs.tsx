"use client";

import { motion } from "motion/react";
import { GuardedLink } from "@/components/app-shell/guarded-link";
import { useSelectionLens } from "@/components/liquid-glass/selection-lens";
import { cn } from "@/lib/utils";

/**
 * Transactions and Review as two tabs of one place: a Liquid Glass segmented control whose raised
 * knob glides between segments, and turns into a magnifying lens while dragged. Each tab is still
 * its own route, so deep links (`?selected=`), Back and the review queue's shortcuts keep working.
 */
export function RecordTabs({ current, toReview }: { current: "all" | "review"; toReview: number | null }) {
  const { attach, handlers, lens } = useSelectionLens<HTMLElement>();
  const tabs = [
    { key: "all", label: "All", href: "/transactions", count: null },
    { key: "review", label: "To review", href: "/review", count: toReview },
  ] as const;
  return (
    <nav ref={attach} aria-label="Transactions" className="lg-static mt-4 inline-flex touch-none rounded-full p-1 select-none" {...handlers}>
      <ul className="flex">
        {tabs.map((tab) => {
          const active = tab.key === current;
          return (
            <li key={tab.key}>
              <GuardedLink
                href={tab.href}
                aria-current={active ? "page" : undefined}
                draggable={false}
                className={cn(
                  "relative flex h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-colors",
                  active ? "text-ink" : "text-ink-soft hover:text-ink",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="record-tab-active"
                    className="lg-knob absolute inset-0 rounded-full"
                    transition={{ type: "spring", stiffness: 420, damping: 30 }}
                  />
                )}
                <span className="relative">{tab.label}</span>
                {tab.count ? (
                  <span className="relative grid h-5 min-w-5 place-items-center rounded-full bg-ink px-1.5 text-[11px] text-white tabular-nums">
                    {tab.count}
                  </span>
                ) : null}
              </GuardedLink>
            </li>
          );
        })}
      </ul>
      {lens}
    </nav>
  );
}
