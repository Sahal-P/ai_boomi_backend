"use client";

import { motion } from "motion/react";
import { GuardedLink } from "@/components/app-shell/guarded-link";
import { cn } from "@/lib/utils";

/**
 * Transactions and Review as two tabs of one place. Each tab is still its own route, so deep
 * links (`?selected=`), Back and the review queue's shortcuts keep working.
 */
export function RecordTabs({ current, toReview }: { current: "all" | "review"; toReview: number | null }) {
  const tabs = [
    { key: "all", label: "All", href: "/transactions", count: null },
    { key: "review", label: "To review", href: "/review", count: toReview },
  ] as const;
  return (
    <nav aria-label="Transactions" className="surface mt-4 inline-flex rounded-full p-1">
      <ul className="flex">
        {tabs.map((tab) => {
          const active = tab.key === current;
          return (
            <li key={tab.key}>
              <GuardedLink
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-colors",
                  active ? "text-white" : "text-ink-soft hover:text-ink",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="record-tab-active"
                    className="absolute inset-0 rounded-full bg-ink shadow-lift"
                    transition={{ type: "spring", stiffness: 420, damping: 36 }}
                  />
                )}
                <span className="relative">{tab.label}</span>
                {tab.count ? (
                  <span
                    className={cn(
                      "relative grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-[11px] tabular-nums",
                      active ? "bg-white text-ink" : "bg-ink text-white",
                    )}
                  >
                    {tab.count}
                  </span>
                ) : null}
              </GuardedLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
