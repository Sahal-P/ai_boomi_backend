"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useSvgId } from "@/components/illustrations/kit";
import { useGlassTier } from "@/components/liquid-glass/glass-store";
import { displacementMap, mapKey, type MapRequest } from "@/lib/liquid-glass/maps";

export type LiquidGlassOptions = {
  /** Width of the curved bezel in CSS px (clamped to the shape). */
  bezel?: number;
  /** How thick the glass is, i.e. how strongly its rim bends what is behind it. */
  thickness?: number;
  /** Index of refraction (glass ≈ 1.5). */
  ior?: number;
  /** Magnify the face, as the drag lens does (1 = none). */
  magnify?: number;
  /** 0–1: split red, green and blue slightly at the rim (small lenses only; costs 3 passes). */
  dispersion?: number;
  /** Turn refraction off while the element is hidden or idle. */
  enabled?: boolean;
};

type Geometry = { width: number; height: number; radius: number };
type Encoded = { href: string; scale: number };

const cache = new Map<string, Encoded>();
const CACHE_LIMIT = 40;

/** Draws a displacement map into a PNG data URL; maps repeat (same sizes), so they are cached. */
function encode(request: MapRequest): Encoded | null {
  const key = mapKey(request);
  const hit = cache.get(key);
  if (hit) {
    cache.delete(key);
    cache.set(key, hit);
    return hit;
  }
  const map = displacementMap(request);
  const canvas = document.createElement("canvas");
  canvas.width = map.width;
  canvas.height = map.height;
  const context = canvas.getContext("2d");
  if (!context) return null;
  const image = context.createImageData(map.width, map.height);
  image.data.set(map.data);
  context.putImageData(image, 0, 0);
  const encoded = { href: canvas.toDataURL("image/png"), scale: map.scale };
  cache.set(key, encoded);
  const oldest = cache.keys().next();
  if (cache.size > CACHE_LIMIT && !oldest.done) cache.delete(oldest.value);
  return encoded;
}

/** The element's own corner radius, so the map always matches the CSS shape. */
function cornerRadius(node: HTMLElement, width: number, height: number) {
  const value = getComputedStyle(node).borderTopLeftRadius;
  const radius = value.endsWith("%") ? (parseFloat(value) / 100) * width : parseFloat(value);
  return Math.min(Number.isFinite(radius) ? radius : 0, width / 2, height / 2);
}

const half = (value: number) => Math.round(value * 2) / 2;

/**
 * Real refraction for one glass element (Chromium only; see `lib/liquid-glass/tier.ts`). Pass
 * `attach` as the element's ref and render `filter` anywhere in the document. The element gets
 * `--lg-refract: url(#…)` and `data-lg-refract`, which globals.css puts in its backdrop filter
 * ahead of the material's frost, saturation and brightness. The map follows the element's size and
 * corner radius; refraction then *materializes* by ramping the lensing in, as Apple's glass does.
 */
export function useLiquidGlass<T extends HTMLElement>({
  bezel = 14,
  thickness = 16,
  ior = 1.5,
  magnify = 1,
  dispersion = 0,
  enabled = true,
}: LiquidGlassOptions = {}): { attach: (node: T | null) => void; filter: ReactNode } {
  const id = useSvgId("lg");
  const tier = useGlassTier();
  const active = tier === "refract" && enabled;
  const [node, setNode] = useState<T | null>(null);
  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const filterRef = useRef<SVGFilterElement>(null);
  const materialized = useRef(false);
  const attach = useCallback((value: T | null) => setNode(value), []);

  useEffect(() => {
    if (!node || !active) return;
    const observer = new ResizeObserver(([entry]) => {
      const box = entry?.borderBoxSize?.[0];
      const width = box?.inlineSize ?? node.offsetWidth;
      const height = box?.blockSize ?? node.offsetHeight;
      if (width < 4 || height < 4) {
        setGeometry(null);
        return;
      }
      const next = { width: half(width), height: half(height), radius: half(cornerRadius(node, width, height)) };
      setGeometry((current) =>
        current && current.width === next.width && current.height === next.height && current.radius === next.radius ? current : next,
      );
    });
    observer.observe(node, { box: "border-box" });
    return () => observer.disconnect();
  }, [node, active]);

  const encoded = useMemo(() => {
    if (!active || !geometry) return null;
    // Big panels are mostly flat face: a half-resolution map stretched back is indistinguishable.
    const area = geometry.width * geometry.height;
    const resolution = area > 120_000 ? 0.5 : Math.min(window.devicePixelRatio || 1, 2);
    return encode({ ...geometry, bezel, thickness, ior, magnify, resolution });
  }, [active, geometry, bezel, thickness, ior, magnify]);

  const ready = Boolean(active && geometry && encoded);

  // Glass that is switched off and on again (the landing nav leaving the yellow hero) materializes
  // afresh each time.
  useEffect(() => {
    if (!active) materialized.current = false;
  }, [active]);

  useEffect(() => {
    if (!node || !ready) return;
    node.style.setProperty("--lg-refract", `url(#${id})`);
    node.dataset.lgRefract = "";
    return () => {
      node.style.removeProperty("--lg-refract");
      delete node.dataset.lgRefract;
    };
  }, [node, ready, id]);

  useEffect(() => {
    const filter = filterRef.current;
    if (!filter || !encoded) return;
    const maps = [...filter.querySelectorAll<SVGFEDisplacementMapElement>("feDisplacementMap")];
    const set = (progress: number) => {
      for (const map of maps) map.setAttribute("scale", String(encoded.scale * Number(map.dataset.factor ?? 1) * progress));
    };
    if (materialized.current || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      materialized.current = true;
      set(1);
      return;
    }
    // Materialize: the lensing ramps in rather than the glass fading in.
    const start = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const progress = Math.min((now - start) / 420, 1);
      set(1 - (1 - progress) ** 3);
      if (progress < 1) frame = requestAnimationFrame(step);
      else materialized.current = true;
    });
    return () => cancelAnimationFrame(frame);
  }, [encoded]);

  const filter =
    ready && geometry && encoded ? (
      <svg aria-hidden="true" focusable="false" width="0" height="0" className="pointer-events-none absolute size-0 overflow-hidden">
        <filter
          ref={filterRef}
          id={id}
          x="0"
          y="0"
          width={geometry.width}
          height={geometry.height}
          filterUnits="userSpaceOnUse"
          primitiveUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB"
        >
          <feImage href={encoded.href} x="0" y="0" width={geometry.width} height={geometry.height} preserveAspectRatio="none" result="map" />
          {dispersion > 0 ? (
            <>
              <feDisplacementMap in="SourceGraphic" in2="map" xChannelSelector="R" yChannelSelector="G" data-factor="1" result="bent-r" />
              <feColorMatrix in="bent-r" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="red" />
              <feDisplacementMap in="SourceGraphic" in2="map" xChannelSelector="R" yChannelSelector="G" data-factor={1 - 0.08 * dispersion} result="bent-g" />
              <feColorMatrix in="bent-g" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="green" />
              <feDisplacementMap in="SourceGraphic" in2="map" xChannelSelector="R" yChannelSelector="G" data-factor={1 - 0.16 * dispersion} result="bent-b" />
              <feColorMatrix in="bent-b" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="blue" />
              <feBlend in="red" in2="green" mode="screen" result="red-green" />
              <feBlend in="red-green" in2="blue" mode="screen" />
            </>
          ) : (
            <feDisplacementMap in="SourceGraphic" in2="map" xChannelSelector="R" yChannelSelector="G" />
          )}
        </filter>
      </svg>
    ) : null;

  return { attach, filter };
}
