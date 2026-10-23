"use client";

import { useThree } from "@react-three/fiber";
import { useEffect, type RefObject } from "react";

import { gsap } from "@/components/motion/gsap";

type TickerFrameloopProps = {
  /** Rendering pauses while this reads false (off-screen, hidden page). */
  active?: RefObject<boolean>;
};

/**
 * Renders a `<Canvas frameloop="never">` from GSAP's ticker, after Lenis and ScrollTrigger
 * have updated for the same tick. R3F's clock receives seconds since mount, so `delta`
 * in useFrame stays frame-rate independent.
 */
export function TickerFrameloop({ active }: TickerFrameloopProps) {
  const advance = useThree((state) => state.advance);

  useEffect(() => {
    const start = gsap.ticker.time;
    const tick = (time: number) => {
      if (active && !active.current) return;
      advance(time - start);
    };
    gsap.ticker.add(tick);
    return () => gsap.ticker.remove(tick);
  }, [active, advance]);

  return null;
}
