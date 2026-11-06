import type { ReactNode } from "react";
import { AdminGate } from "@/components/admin/admin-gate";
import { AdminNav } from "@/components/admin/admin-nav";
import { OfflineBanner } from "@/components/app-shell/offline-banner";
import { RouteTransition } from "@/components/app-shell/route-transition";
import { AppMotion } from "@/components/motion/app-motion";

// Outside the household (app) group: its gate would send people to the household sign-in.
export default function AdminConsoleLayout({ children }: { children: ReactNode }) {
  return (
    <AdminGate>
      <AppMotion>
        <div className="app-shell bg-field bg-wallpaper relative min-h-dvh">
          <a
            href="#main-content"
            className="sr-only rounded-full bg-ink px-4 py-3 text-white focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50"
          >
            Skip to content
          </a>
          <AdminNav />
          <main
            id="main-content"
            tabIndex={-1}
            className="px-4 pt-[5.25rem] pb-28 outline-none min-[390px]:px-6 sm:px-8 lg:pt-10 lg:pr-10 lg:pb-12 lg:pl-[300px]"
          >
            <div className="mx-auto max-w-6xl">
              <OfflineBanner />
              <RouteTransition>{children}</RouteTransition>
            </div>
          </main>
        </div>
      </AppMotion>
    </AdminGate>
  );
}
