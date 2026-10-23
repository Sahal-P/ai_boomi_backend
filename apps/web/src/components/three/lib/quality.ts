import { useSyncExternalStore } from "react";

import { webglRenderer } from "./webgl";

export type QualityTier = "high" | "medium" | "low";

const ORDER: readonly QualityTier[] = ["high", "medium", "low"];
const listeners = new Set<() => void>();
let currentTier: QualityTier | null = null;
let locked = false;

function isTier(value: string | null): value is QualityTier {
  return value === "high" || value === "medium" || value === "low";
}

function detectInitialTier(): QualityTier {
  // `?quality=high|medium|low` pins a tier for QA and disables automatic downgrades.
  const forced = new URLSearchParams(window.location.search).get("quality");
  if (isTier(forced)) {
    locked = true;
    return forced;
  }
  if (/swiftshader|llvmpipe|software/i.test(webglRenderer())) return "low";
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches;
  const cores = navigator.hardwareConcurrency || 4;
  const smallScreen = Math.min(window.innerWidth, window.innerHeight) < 600;
  if (coarsePointer && (smallScreen || cores <= 4)) return "low";
  if (coarsePointer || cores <= 4) return "medium";
  return "high";
}

function getTier(): QualityTier {
  currentTier ??= detectInitialTier();
  return currentTier;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Steps every canvas down one tier. Ignored while the page is hidden or throttled in the
 * background, where low frame rates say nothing about the GPU.
 */
export function downgradeQuality(): void {
  if (locked || document.visibilityState !== "visible") return;
  const next = ORDER[ORDER.indexOf(getTier()) + 1];
  if (!next) return;
  currentTier = next;
  listeners.forEach((listener) => listener());
}

export function useQualityTier(): QualityTier {
  return useSyncExternalStore(subscribe, getTier, () => "medium");
}

/** Device-pixel-ratio range each tier may adapt within (PerformanceMonitor factor 0 → 1). */
const DPR_RANGE: Record<QualityTier, readonly [number, number]> = {
  high: [1, 1.75],
  medium: [0.9, 1.5],
  low: [0.75, 1.25],
};

/** DPR for a PerformanceMonitor factor, capped by the screen and rounded to limit resizes. */
export function dprFor(tier: QualityTier, factor: number): number {
  const [min, max] = DPR_RANGE[tier];
  const device = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
  const value = Math.min(device, min + (max - min) * Math.min(Math.max(factor, 0), 1));
  return Math.round(value * 20) / 20;
}
