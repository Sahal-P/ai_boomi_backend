"use client";

import { useInView } from "motion/react";
import dynamic from "next/dynamic";
import { useEffect, useRef, useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

import { useWebGLSupport } from "./lib/webgl";
import type { SceneSpec } from "./scene-spec";
import { WebGLBoundary } from "./webgl-boundary";

const SceneView = dynamic(() => import("./scene-view"), { ssr: false });
const SceneLayer = dynamic(() => import("./scene-layer"), { ssr: false });

// How many slots currently want 3D. The shared canvas (and three.js) loads only when > 0.
let demand = 0;
const listeners = new Set<() => void>();

function changeDemand(delta: number) {
  demand += delta;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

type SceneSlotProps = {
  spec: SceneSpec;
  className?: string;
};

/**
 * Reserves layout space for a 3D illustration; the scene mounts into the shared
 * SceneLayer when the slot first nears the viewport, and its reveal choreography starts
 * once 40% of the slot is actually visible. Size the slot with `className`.
 * DOM that must sit above 3D (buttons over a scene) needs `relative z-20`.
 */
export function SceneSlot({ spec, className }: SceneSlotProps) {
  const slot = useRef<HTMLDivElement>(null);
  const webgl = useWebGLSupport();
  const near = useInView(slot, { once: true, margin: "400px 0px" }) && webgl;
  const revealed = useInView(slot, { once: true, amount: 0.4 });

  useEffect(() => {
    if (!near) return;
    changeDemand(1);
    return () => changeDemand(-1);
  }, [near]);

  return (
    <div ref={slot} aria-hidden="true" className={cn("relative", className)}>
      {near ? <SceneView spec={spec} revealed={revealed} className="absolute inset-0" /> : null}
    </div>
  );
}

/** Mount once in any layout or page that may contain SceneSlots. */
export function SceneLayerMount() {
  const needed = useSyncExternalStore(subscribe, () => demand > 0, () => false);
  return needed ? (
    <WebGLBoundary>
      <SceneLayer />
    </WebGLBoundary>
  ) : null;
}
