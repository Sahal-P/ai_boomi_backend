"use client";

import { PerformanceMonitor } from "@react-three/drei";
import { useThree } from "@react-three/fiber";

import { downgradeQuality, dprFor, type QualityTier } from "./quality";

/** Starting point inside each tier's DPR range; the monitor moves it in 10% steps. */
export const INITIAL_FACTOR = 0.6;
const STEP = 0.1;

/**
 * Holding 60 fps is the criterion on any display: frequent misses (average below 57) step
 * the resolution down; it only climbs while frames are held (59.5+ at 60 Hz, 80+ on 120 Hz
 * panels — never trading sharpness to chase 120 fps).
 */
const bounds = (refreshRate: number): [number, number] => (refreshRate > 100 ? [57, 80] : [57, 59.5]);

/**
 * Adaptive resolution first, adaptive features second. Sustained misses lower the pixel
 * ratio within the tier's range; only when it bottoms out does every canvas step down a
 * quality tier. If the ratio keeps flip-flopping around the budget, it settles one step
 * below the last level instead of oscillating.
 */
export function AdaptiveQuality({ tier }: { tier: QualityTier }) {
  const setDpr = useThree((state) => state.setDpr);
  return (
    <PerformanceMonitor
      factor={INITIAL_FACTOR}
      step={STEP}
      bounds={bounds}
      flipflops={4}
      onChange={({ factor }) => setDpr(dprFor(tier, factor))}
      onDecline={({ factor }) => {
        if (factor <= 0) downgradeQuality();
      }}
      onFallback={({ factor }) => setDpr(dprFor(tier, factor - STEP))}
    />
  );
}
