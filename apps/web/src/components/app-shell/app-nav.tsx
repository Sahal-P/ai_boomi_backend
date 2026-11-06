"use client";

import { ArrowLeftRight, ChartPie, House, Plus, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { usePathname } from "next/navigation";
import { useMemo, useState, type PointerEvent } from "react";

import { AccountMenu, AccountPanel } from "@/components/app-shell/account-controls";
import { GuardedLink } from "@/components/app-shell/guarded-link";
import { Brand } from "@/components/brand";
import { mergeRefs } from "@/components/liquid-glass/merge-refs";
import { ScrollEdge, useScrolled } from "@/components/liquid-glass/scroll-edge";
import { useSelectionLens } from "@/components/liquid-glass/selection-lens";
import { useLiquidGlass } from "@/components/liquid-glass/use-liquid-glass";
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

const GLIDE = { type: "spring", stiffness: 520, damping: 38, mass: 0.7 } as const;

/** The selected item's well: Apple's selection platter, gliding between items on a gel spring. */
function Platter({ layoutId }: { layoutId: string }) {
  return (
    <motion.span
      layoutId={layoutId}
      className="lg-platter absolute inset-0 rounded-full"
      transition={{ type: "spring", stiffness: 420, damping: 30 }}
    />
  );
}

/**
 * Liquid Glass navigation: an inset glass sidebar (desktop); on phones a glass account button over
 * the top scroll edge, and a floating glass tab pill with a drag lens beside a tinted-glass +.
 */
export function AppNav() {
  const pathname = usePathname();
  const quickAdd = useQuickAdd();
  const scrolled = useScrolled();
  // The mouse's highlight in the sidebar glides from item to item; `jump` places it without a glide
  // when the pointer first arrives.
  const [hover, setHover] = useState<{ top: number; height: number; jump: boolean } | null>(null);
  const highlight = (event: PointerEvent<HTMLElement>) => {
    if (event.pointerType !== "mouse") return;
    const { offsetTop: top, offsetHeight: height } = event.currentTarget;
    setHover((previous) => ({ top, height, jump: previous === null }));
  };
  // Destructured: the React Compiler treats an object whose member is passed as `ref` as a ref.
  const { attach: attachSidebar, filter: sidebarFilter } = useLiquidGlass<HTMLElement>({ bezel: 22, thickness: 20 });
  const { attach: attachPillGlass, filter: pillFilter } = useLiquidGlass<HTMLElement>({ bezel: 16, thickness: 18 });
  const { attach: attachLens, handlers: lensHandlers, lens } = useSelectionLens<HTMLElement>();
  const attachPill = useMemo(() => mergeRefs(attachPillGlass, attachLens), [attachPillGlass, attachLens]);

  return (
    <>
      {/* Content never scrolls under the sidebar: like a macOS 26 sidebar it shows the wallpaper's
          colour, bent at its rim, and catches the light where the mouse is. */}
      <aside
        ref={attachSidebar}
        className="lg-thick lg-sidebar fixed top-3 bottom-3 left-3 z-40 hidden w-[264px] flex-col rounded-[28px] p-4 lg:flex"
      >
        {sidebarFilter}
        <Brand className="px-2 pt-1" />
        <Button className="mt-7 w-full" onClick={quickAdd.open}>
          <Plus aria-hidden="true" /> Add entry
        </Button>
        <nav aria-label="App navigation" className="mt-5 flex-1">
          <ul className="relative space-y-1" onPointerLeave={() => setHover(null)}>
            <motion.span
              aria-hidden="true"
              className="lg-hover pointer-events-none absolute inset-x-0 top-0 rounded-full"
              initial={false}
              animate={hover ? { y: hover.top, height: hover.height, opacity: 1 } : { opacity: 0 }}
              transition={
                hover?.jump
                  ? { y: { duration: 0 }, height: { duration: 0 }, opacity: { duration: 0.15 } }
                  : { y: GLIDE, height: GLIDE, opacity: { duration: 0.2 } }
              }
            />
            {APP_NAVIGATION.map(({ label, href, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href} onPointerEnter={highlight}>
                  <GuardedLink
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-11 items-center gap-3 rounded-full px-3.5 text-sm font-semibold transition-colors",
                      active ? "text-ink" : "text-ink-soft hover:text-ink",
                    )}
                  >
                    {active ? <Platter layoutId="app-nav-active" /> : null}
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

      {/* Content dissolves under the top edge once scrolled (iOS 27's uniform bar on phones; on desktop
          a shorter band that fades out under the floating toolbar) and, on phones, under the tab bar. */}
      <ScrollEdge top={scrolled} bottom />
      {/* Phones: no bar behind the wordmark, and the account button is a small glass circle. */}
      <header data-scroll-edge="top" className="fixed inset-x-3 top-3 z-40 flex h-14 items-center justify-between pr-1.5 pl-2 lg:hidden">
        <Brand />
        <AccountMenu />
      </header>

      {/* The tab pill and the + step aside together while typing (globals.css). */}
      <div className="app-tabbar fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-40 flex items-center gap-2 lg:hidden">
        <nav
          ref={attachPill}
          aria-label="App navigation"
          data-scroll-edge="bottom"
          className="lg min-w-0 flex-1 touch-none rounded-full p-1.5 select-none"
          {...lensHandlers}
        >
          {pillFilter}
          {/* Every tab keeps its label; content-sized cells so "Transactions" fits at 320 px
              beside the +. Press and slide to choose with the lens. */}
          <ul className="flex">
            {APP_NAVIGATION.map(({ label, href, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href} className="min-w-11 flex-auto">
                  <GuardedLink
                    href={href}
                    aria-current={active ? "page" : undefined}
                    draggable={false}
                    className={cn(
                      "relative flex h-12 flex-col items-center justify-center gap-1 rounded-full px-1 text-[11px] leading-none font-semibold whitespace-nowrap",
                      active ? "px-2.5 text-ink" : "text-ink-soft",
                    )}
                  >
                    {active ? <Platter layoutId="app-tab-active" /> : null}
                    <Icon className="relative size-[18px]" aria-hidden="true" />
                    <span className="relative">{label}</span>
                  </GuardedLink>
                </li>
              );
            })}
          </ul>
        </nav>
        {/* A sibling, not a child: glass with a backdrop filter is its children's backdrop root, so
            a lens inside the pill would only see the pill's own layer and ghost the labels. */}
        {lens}
        <Button size="icon" aria-label="Add entry" className="size-[60px] shrink-0" onClick={quickAdd.open}>
          <Plus className="size-6" aria-hidden="true" />
        </Button>
      </div>
    </>
  );
}
