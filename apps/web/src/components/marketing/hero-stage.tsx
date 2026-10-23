"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { ScrollTrigger, useGSAP } from "@/components/motion/gsap";
import type { HeroPointer } from "@/components/three/hero/hero-scene";
import { supportsWebGL } from "@/components/three/lib/webgl";
import { WebGLBoundary } from "@/components/three/webgl-boundary";

const HeroCanvas = dynamic(() => import("@/components/three/hero/hero-canvas"), { ssr: false });

/**
 * Hosts the hero WebGL scene. Pointer and scroll live in refs so the 3D loop reads them
 * every frame without re-rendering React; scroll comes from ScrollTrigger, which updates
 * in the same GSAP tick as Lenis and the canvas. The CSS poster underneath is what users
 * see before WebGL is ready (or if it never is).
 */
export function HeroStage() {
  const root = useRef<HTMLDivElement>(null);
  const pointer = useRef<HeroPointer>({ x: 0, y: 0 });
  const progress = useRef(0);
  const [mountCanvas, setMountCanvas] = useState(false);

  // Start WebGL after first paint so the CSS headline animation is never janked by shader compiles.
  useEffect(() => {
    if (typeof window.requestIdleCallback === "function") {
      const handle = window.requestIdleCallback(() => setMountCanvas(supportsWebGL()), { timeout: 900 });
      return () => window.cancelIdleCallback(handle);
    }
    const timer = window.setTimeout(() => setMountCanvas(supportsWebGL()), 350);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const onPointerMove = (event: PointerEvent) => {
      pointer.current = {
        x: (event.clientX / window.innerWidth) * 2 - 1,
        y: -((event.clientY / window.innerHeight) * 2 - 1),
      };
    };
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    return () => window.removeEventListener("pointermove", onPointerMove);
  }, []);

  useGSAP(() => {
    const section = root.current?.parentElement;
    if (!section) return;
    ScrollTrigger.create({
      trigger: section,
      start: "top top",
      end: "bottom top",
      onUpdate: (self) => {
        progress.current = self.progress;
      },
    });
  });

  return (
    <div ref={root} aria-hidden="true" className="absolute inset-0">
      <div className="absolute inset-0 bg-[radial-gradient(38rem_26rem_at_70%_64%,rgba(178,107,255,0.3),transparent_70%),radial-gradient(34rem_24rem_at_78%_26%,rgba(255,244,230,0.95),transparent_70%),radial-gradient(30rem_22rem_at_92%_88%,rgba(255,95,210,0.18),transparent_70%)]" />
      {mountCanvas ? (
        <WebGLBoundary>
          <HeroCanvas pointer={pointer} progress={progress} />
        </WebGLBoundary>
      ) : null}
    </div>
  );
}
