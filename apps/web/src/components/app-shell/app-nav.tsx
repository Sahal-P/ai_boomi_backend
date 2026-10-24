"use client";

import {
  ArrowLeftRight,
  Inbox,
  LayoutDashboard,
  ListChecks,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { motion } from "motion/react";
import { usePathname } from "next/navigation";

import { AccountMenu, AccountPanel } from "@/components/app-shell/account-controls";
import { GuardedLink } from "@/components/app-shell/guarded-link";
import { Brand } from "@/components/brand";
import { cn } from "@/lib/utils";

export const APP_NAVIGATION = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard, mobile: true },
  { label: "Transactions", href: "/transactions", icon: ArrowLeftRight, mobile: true },
  { label: "Review", href: "/review", icon: ListChecks, mobile: true },
  { label: "Ask", href: "/assistant", icon: Sparkles, mobile: true },
  { label: "Sources", href: "/sources", icon: Inbox, mobile: true },
  { label: "Privacy", href: "/privacy", icon: ShieldCheck, mobile: false },
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/sources") {
    return ["/sources", "/connect", "/import"].some(
      (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
    );
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Floating glass sidebar (desktop); compact header and five-tab bar (phones). */
export function AppNav() {
  const pathname = usePathname();

  return (
    <>
      <aside className="glass fixed top-3 bottom-3 left-3 z-40 hidden w-[264px] flex-col rounded-[1.75rem] p-4 lg:flex">
        <Brand className="px-2 pt-1" />
        <nav aria-label="App navigation" className="mt-8 flex-1">
          <ul className="space-y-1">
            {APP_NAVIGATION.map(({ label, href, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href}>
                  <GuardedLink
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-11 items-center gap-3 rounded-2xl px-3 text-sm font-semibold transition-colors",
                      active ? "text-ink" : "text-ink-soft hover:bg-white/60 hover:text-ink",
                    )}
                  >
                    {active ? (
                      <motion.span
                        layoutId="app-nav-active"
                        className="absolute inset-0 rounded-2xl bg-white shadow-soft"
                        transition={{ type: "spring", stiffness: 420, damping: 36 }}
                      />
                    ) : null}
                    <Icon
                      className={cn("relative size-[18px]", active && "text-violet")}
                      aria-hidden="true"
                    />
                    <span className="relative">{label}</span>
                  </GuardedLink>
                </li>
              );
            })}
          </ul>
        </nav>
        <AccountPanel />
      </aside>

      {/* Near-opaque on phones: content (including the dark estimate card) scrolls beneath,
          and labels must keep their contrast over it. */}
      <header className="glass fixed inset-x-3 top-3 z-40 flex h-14 items-center justify-between rounded-full bg-white/[0.94] pr-1.5 pl-4 lg:hidden">
        <Brand />
        <AccountMenu />
      </header>

      <nav
        aria-label="App navigation"
        className="app-tabbar glass fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-40 rounded-full bg-white/[0.94] p-1.5 lg:hidden"
      >
        {/* Content-sized cells so "Transactions" fits at 320px without shrinking labels. */}
        <ul className="flex">
          {APP_NAVIGATION.filter((item) => item.mobile).map(({ label, href, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href} className="min-w-11 flex-auto">
                <GuardedLink
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex h-12 flex-col items-center justify-center gap-1 rounded-full px-1 text-[11px] leading-none font-semibold whitespace-nowrap",
                    active ? "text-ink" : "text-ink-soft",
                  )}
                >
                  {active ? (
                    <motion.span
                      layoutId="app-tab-active"
                      className="absolute inset-0 rounded-full bg-white shadow-soft"
                      transition={{ type: "spring", stiffness: 420, damping: 36 }}
                    />
                  ) : null}
                  <Icon
                    className={cn("relative size-[18px]", active && "text-violet")}
                    aria-hidden="true"
                  />
                  <span className="relative">{label}</span>
                </GuardedLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
