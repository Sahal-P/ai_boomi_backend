import { ViewTransition, type ReactNode } from "react";

import { AppNav } from "@/components/app-shell/app-nav";
import { SceneLayerMount } from "@/components/three/scene-slot";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-aurora relative min-h-screen">
      <a
        href="#main-content"
        className="sr-only rounded-full bg-ink px-4 py-3 text-white focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50"
      >
        Skip to content
      </a>
      <AppNav />
      <SceneLayerMount />
      <main id="main-content" tabIndex={-1} className="px-4 pt-24 pb-28 outline-none sm:px-8 lg:pt-10 lg:pr-10 lg:pb-12 lg:pl-[300px]">
        <div className="mx-auto max-w-6xl">
          <ViewTransition default="page">{children}</ViewTransition>
        </div>
      </main>
    </div>
  );
}
