"use client";

import { ArrowLeftRight, Inbox, LayoutDashboard, ListChecks, ShieldCheck, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Brand } from "@/components/brand";
import { useHealth } from "@/hooks/use-health";
import { cn } from "@/lib/utils";

export const APP_NAVIGATION = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, mobile: true },
  { label: "Transactions", href: "/transactions", icon: ArrowLeftRight, mobile: true },
  { label: "Review", href: "/review", icon: ListChecks, mobile: true },
  { label: "Assistant", href: "/assistant", icon: Sparkles, mobile: true },
  { label: "Connect", href: "/connect", icon: Inbox, mobile: false },
  { label: "Privacy", href: "/privacy", icon: ShieldCheck, mobile: true },
] as const;

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`) || (href === "/connect" && pathname.startsWith("/import"));
}

function ConnectionDot() {
  const { connection } = useHealth();
  const label =
    connection.state === "connected"
      ? "Live · API connected"
      : connection.state === "checking"
        ? "Checking connection…"
        : connection.state === "degraded"
          ? "Database unavailable"
          : "Backend offline";
  return (
    <p role="status" className="flex items-center gap-2 text-xs font-medium text-ink-soft">
      <span
        className={cn(
          "size-2 rounded-full",
          connection.state === "connected" ? "bg-positive" : connection.state === "checking" ? "animate-pulse bg-ink-subtle" : "bg-warning",
        )}
      />
      {label}
    </p>
  );
}

/** Floating glass sidebar (desktop) and glass tab bar (mobile). */
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
                  <Link
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
                    <Icon className={cn("relative size-[18px]", active && "text-violet")} aria-hidden="true" />
                    <span className="relative">{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <Link
          href="/assistant"
          className="group relative overflow-hidden rounded-2xl bg-[linear-gradient(140deg,#efe9ff,#fbe6f6)] p-4 transition-transform duration-300 ease-out-expo hover:-translate-y-0.5"
        >
          <Sparkles className="size-5 text-violet" aria-hidden="true" />
          <p className="mt-3 text-sm font-semibold text-ink">Ask in Malayalam</p>
          <p lang="ml" className="mt-0.5 text-xs text-ink-soft">
            ഈ മാസം എത്ര ചെലവായി?
          </p>
        </Link>
        <div className="mt-4 px-2">
          <ConnectionDot />
        </div>
      </aside>

      <header className="glass fixed inset-x-3 top-3 z-40 flex h-14 items-center justify-between rounded-full px-4 lg:hidden">
        <Brand />
        <Link href="/connect" className="text-sm font-semibold text-violet">
          Connect
        </Link>
      </header>

      <nav aria-label="App navigation" className="glass fixed inset-x-3 bottom-3 z-40 rounded-full p-1.5 lg:hidden">
        <ul className="grid grid-cols-5">
          {APP_NAVIGATION.filter((item) => item.mobile).map(({ label, href, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex h-12 flex-col items-center justify-center gap-0.5 rounded-full text-[10px] font-semibold",
                    active ? "text-ink" : "text-ink-subtle",
                  )}
                >
                  {active ? (
                    <motion.span
                      layoutId="app-tab-active"
                      className="absolute inset-0 rounded-full bg-white shadow-soft"
                      transition={{ type: "spring", stiffness: 420, damping: 36 }}
                    />
                  ) : null}
                  <Icon className={cn("relative size-[18px]", active && "text-violet")} aria-hidden="true" />
                  <span className="relative">{label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
