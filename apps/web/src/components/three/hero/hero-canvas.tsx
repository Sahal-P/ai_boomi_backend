"use client";

import { Canvas } from "@react-three/fiber";
import { Bloom, EffectComposer, SMAA, ToneMapping } from "@react-three/postprocessing";
import { useInView, useReducedMotion } from "motion/react";
import { ToneMappingMode } from "postprocessing";
import { Suspense, useCallback, useEffect, useRef, useState, type RefObject } from "react";

import { cn } from "@/lib/utils";

import { AdaptiveQuality, INITIAL_FACTOR } from "../lib/adaptive-quality";
import { preloadModels } from "../lib/assets";
import { TickerFrameloop } from "../lib/frameloop";
import { dprFor, useQualityTier, type QualityTier } from "../lib/quality";
import { patchStableSoftShadows } from "../lib/soft-shadows";
import { HeroScene, type HeroPointer } from "./hero-scene";

patchStableSoftShadows();
preloadModels();

/**
 * Restrained grade, budgeted for 60 fps (measured on an M4 at 1440×900, DPR 1.5–1.75):
 * bloom only catches HDR — LED strips and specular glints; sunlit white stays below the
 * threshold — then Khronos Neutral tone mapping and SMAA. Screen-space AO (N8AO) was
 * measured and dropped: it cost ~15 fps even at half resolution and ~5 fps in performance
 * mode, for barely visible contact darkening on a set of floating slabs. Always
 * composited, so the clear colour is tone-mapped identically on every tier.
 */
function Effects({ quality }: { quality: QualityTier }) {
  return (
    <EffectComposer multisampling={0} stencilBuffer={false}>
      {quality === "low" ? (
        <></>
      ) : (
        <Bloom mipmapBlur luminanceThreshold={5} luminanceSmoothing={0.8} intensity={0.6} radius={0.7} />
      )}
      <ToneMapping mode={ToneMappingMode.NEUTRAL} />
      <SMAA />
    </EffectComposer>
  );
}

type HeroCanvasProps = {
  pointer: RefObject<HeroPointer>;
  progress: RefObject<number>;
};

export default function HeroCanvas({ pointer, progress }: HeroCanvasProps) {
  const quality = useQualityTier();
  const reducedMotion = useReducedMotion() ?? false;
  const container = useRef<HTMLDivElement>(null);
  const inView = useInView(container, { margin: "120px" });
  const active = useRef(true);
  const [ready, setReady] = useState(false);
  const onReady = useCallback(() => {
    requestAnimationFrame(() => setReady(true));
  }, []);

  useEffect(() => {
    const update = () => {
      active.current = inView && document.visibilityState === "visible";
    };
    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, [inView]);

  return (
    <div
      ref={container}
      data-hero-canvas={ready ? "ready" : "loading"}
      className={cn(
        "absolute inset-0 transition-opacity duration-[1600ms] ease-out-expo",
        ready ? "opacity-100" : "opacity-0",
      )}
    >
      <Canvas
        shadows="percentage"
        frameloop={reducedMotion ? "demand" : "never"}
        dpr={dprFor(quality, INITIAL_FACTOR)}
        camera={{ position: [1.5, 9.5, 13], fov: 30, near: 0.5, far: 90 }}
        gl={{ antialias: false, powerPreference: "high-performance", stencil: false }}
      >
        <Suspense fallback={null}>
          <HeroScene
            quality={quality}
            reducedMotion={reducedMotion}
            pointer={pointer}
            progress={progress}
            onReady={onReady}
          />
          <Effects quality={quality} />
        </Suspense>
        <AdaptiveQuality tier={quality} />
        {reducedMotion ? null : <TickerFrameloop active={active} />}
      </Canvas>
    </div>
  );
}
