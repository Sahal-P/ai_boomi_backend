"use client";

import { View } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { useReducedMotion } from "motion/react";
import { useEffect } from "react";
import * as THREE from "three";

import { AdaptiveQuality, INITIAL_FACTOR } from "./lib/adaptive-quality";
import { preloadModels } from "./lib/assets";
import { TickerFrameloop } from "./lib/frameloop";
import { dprFor, useQualityTier } from "./lib/quality";

preloadModels();

/** Reduced motion renders on demand: once per scroll or resize, so Views keep tracking their slots. */
function InvalidateOnScroll() {
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => {
    const render = () => invalidate();
    window.addEventListener("scroll", render, { passive: true });
    window.addEventListener("resize", render);
    return () => {
      window.removeEventListener("scroll", render);
      window.removeEventListener("resize", render);
    };
  }, [invalidate]);
  return null;
}

/**
 * One fixed, transparent WebGL canvas for every <SceneSlot> on the page. drei Views
 * scissor it into the slots' rectangles, so many illustrations share a single context.
 * Rendered from the GSAP ticker right after Lenis, so scenes never trail their cards.
 */
export default function SceneLayer() {
  const quality = useQualityTier();
  const reducedMotion = useReducedMotion() ?? false;
  return (
    <Canvas
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, zIndex: 10, pointerEvents: "none" }}
      frameloop={reducedMotion ? "demand" : "never"}
      dpr={dprFor(quality, INITIAL_FACTOR)}
      gl={{
        alpha: true,
        antialias: true,
        powerPreference: "high-performance",
        toneMapping: THREE.NeutralToneMapping,
      }}
    >
      <View.Port />
      <AdaptiveQuality tier={quality} />
      {reducedMotion ? <InvalidateOnScroll /> : <TickerFrameloop />}
    </Canvas>
  );
}
