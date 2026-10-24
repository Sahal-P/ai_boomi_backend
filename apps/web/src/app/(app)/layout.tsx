import type { Metadata } from "next";
import { ViewTransition, type ReactNode } from "react";

import { AppNav } from "@/components/app-shell/app-nav";
import { HouseholdGate } from "@/components/app-shell/household-gate";
import { KeyboardHelp } from "@/components/app-shell/keyboard-help";
import { LeaveGuard } from "@/components/app-shell/leave-guard";
import { OfflineBanner } from "@/components/app-shell/offline-banner";

export const metadata: Metadata = { robots: { index: false, follow: false } };

// Daily screens carry no WebGL: the brand scenes stay on the marketing page (F35).
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <HouseholdGate>
      <div className="app-shell bg-aurora relative min-h-dvh">
        <a
          href="#main-content"
          className="sr-only rounded-full bg-ink px-4 py-3 text-white focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50"
        >
          Skip to content
        </a>
        <AppNav />
        <main
          id="main-content"
          tabIndex={-1}
          className="px-4 pt-[5.25rem] pb-28 outline-none sm:px-8 lg:pt-10 lg:pr-10 lg:pb-12 lg:pl-[300px]"
        >
          <div className="mx-auto max-w-6xl">
            <OfflineBanner />
            <ViewTransition default="page">{children}</ViewTransition>
          </div>
        </main>
        <LeaveGuard />
        <KeyboardHelp />
      </div>
    </HouseholdGate>
  );
}
