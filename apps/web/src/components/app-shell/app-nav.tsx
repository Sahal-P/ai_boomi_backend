"use client";

import { ArrowLeftRight, ChartPie, House, Plus, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { usePathname } from "next/navigation";

import { AccountMenu, AccountPanel } from "@/components/app-shell/account-controls";
import { GuardedLink } from "@/components/app-shell/guarded-link";
import { Brand } from "@/components/brand";
import { useQuickAdd } from "@/components/money/quick-add-provider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Four destinations. Review is a tab inside Transactions; Sources and Privacy & data live in
 *  the account menu, so nothing here competes with the daily tasks. */
export const APP_NAVIGATION = [
  { label: "Home", href: "/dashboard", icon: House },
  { label: "Transactions", href: "/transactions", icon: ArrowLeftRight },
  { label: "Reports", href: "/reports", icon: ChartPie },
  { label: "Ask", href: "/assistant", icon: Sparkles },
] as const;

function isActive(pathname: string, href: string) {
  const prefixes = href === "/transactions" ? ["/transactions", "/review"] : [href];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/** Floating glass sidebar (desktop); compact header, tab pill and a round + (phones). */
export function AppNav() {
  const pathname = usePathname();
  const quickAdd = useQuickAdd();

  return (
    <>
      {/* In-flow glass: content never scrolls under the sidebar, so it needs no blur. */}
      <aside className="surface fixed top-3 bottom-3 left-3 z-40 hidden w-[264px] flex-col rounded-3xl p-4 lg:flex">
        <Brand className="px-2 pt-1" />
        <Button className="mt-7 w-full" onClick={quickAdd.open}>
          <Plus aria-hidden="true" /> Add entry
        </Button>
        <nav aria-label="App navigation" className="mt-5 flex-1">
          <ul className="space-y-1">
            {APP_NAVIGATION.map(({ label, href, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href}>
                  <GuardedLink
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-11 items-center gap-3 rounded-full px-3.5 text-sm font-semibold transition-colors",
                      active ? "text-white" : "text-ink-soft hover:bg-white/60 hover:text-ink",
                    )}
                  >
                    {active ? (
                      <motion.span
                        layoutId="app-nav-active"
                        className="absolute inset-0 rounded-full bg-ink shadow-lift"
                        transition={{ type: "spring", stiffness: 420, damping: 36 }}
                      />
                    ) : null}
                    <Icon className="relative size-[18px]" aria-hidden="true" />
                    <span className="relative">{label}</span>
                  </GuardedLink>
                </li>
              );
            })}
          </ul>
        </nav>
        <AccountPanel />
      </aside>

      {/* Near-opaque blurred glass on phones: content (black pills included) scrolls beneath,
          and labels must keep their contrast over it. */}
      <header className="glass fixed inset-x-3 top-3 z-40 flex h-14 items-center justify-between rounded-full bg-white/[0.9] pr-1.5 pl-4 lg:hidden">
        <Brand />
        <AccountMenu />
      </header>

      {/* The tab pill and the + step aside together while typing (globals.css). */}
      <div className="app-tabbar fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-40 flex items-center gap-2 lg:hidden">
        <nav aria-label="App navigation" className="glass min-w-0 flex-1 rounded-full bg-white/[0.94] p-1.5">
          {/* The reference's black active capsule, and every tab keeps its label. Content-sized
              cells so "Transactions" fits at 320 px beside the +. */}
          <ul className="flex">
            {APP_NAVIGATION.map(({ label, href, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href} className="min-w-11 flex-auto">
                  <GuardedLink
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-12 flex-col items-center justify-center gap-1 rounded-full px-1 text-[11px] leading-none font-semibold whitespace-nowrap",
                      active ? "px-2.5 text-white" : "text-ink-soft",
                    )}
                  >
                    {active ? (
                      <motion.span
                        layoutId="app-tab-active"
                        className="absolute inset-0 rounded-full bg-ink shadow-lift"
                        transition={{ type: "spring", stiffness: 420, damping: 36 }}
                      />
                    ) : null}
                    <Icon className="relative size-[18px]" aria-hidden="true" />
                    <span className="relative">{label}</span>
                  </GuardedLink>
                </li>
              );
            })}
          </ul>
        </nav>
        <Button size="icon" aria-label="Add entry" className="size-[60px] shrink-0" onClick={quickAdd.open}>
          <Plus className="size-6" aria-hidden="true" />
        </Button>
      </div>
    </>
  );
}
