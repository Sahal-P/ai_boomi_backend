"use client";

import { ReactLenis, useLenis } from "lenis/react";
import { useReducedMotion } from "motion/react";
import { useEffect, type ReactNode } from "react";

import { gsap, ScrollTrigger } from "./gsap";

const updateScrollTrigger = () => ScrollTrigger.update();

/** Runs Lenis first in each GSAP tick and feeds ScrollTrigger the smoothed scroll. */
function LenisTicker() {
  const lenis = useLenis(updateScrollTrigger);

  useEffect(() => {
    if (!lenis) return;
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick, false, true);
    ScrollTrigger.refresh();
    return () => gsap.ticker.remove(tick);
  }, [lenis]);

  return null;
}

/**
 * Weighted inertial scrolling for the marketing page. Always mounted (stable tree for
 * hydration); smoothing is switched off for reduced motion.
 */
export function SmoothScroll({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion() === true;
  return (
    <ReactLenis
      root
      options={{ lerp: 0.1, wheelMultiplier: 0.95, smoothWheel: !reduced, autoRaf: false, anchors: { offset: -80 } }}
    >
      <LenisTicker />
      {children}
    </ReactLenis>
  );
}
