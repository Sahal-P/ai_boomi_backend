"use client";

import { useId, type ReactNode } from "react";

/** Sunflower, the only colour fill in FinBoy's line art. */
export const SUNFLOWER = "#fed234";

/** A per-instance SVG id: a copy elsewhere on the page (even a hidden one) can't break this one. */
export function useSvgId(prefix: string) {
  return `${prefix}-${useId().replace(/[^\w-]/g, "")}`;
}

/**
 * Line-art frame: ink strokes in currentColor (forced colours adapt), white and sunflower fills,
 * halftone shading from a 4.5-unit dot grid — the same dot language as the thinking orbs.
 * Decorative only.
 */
export function Art({ viewBox, className, children }: { viewBox: string; className?: string; children: (dots: string) => ReactNode }) {
  const dots = useSvgId("fb-dots");
  return (
    <svg
      viewBox={viewBox}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <pattern id={dots} width="4.5" height="4.5" patternUnits="userSpaceOnUse">
          <circle cx="2.25" cy="2.25" r="1.05" fill="currentColor" stroke="none" />
        </pattern>
      </defs>
      {children(`url(#${dots})`)}
    </svg>
  );
}

/** Four-point sparkle centred on (x, y). */
export function Sparkle({ x, y, r = 10 }: { x: number; y: number; r?: number }) {
  return (
    <path
      transform={`translate(${x} ${y}) scale(${r / 10})`}
      d="M0-10C1.2-2 2-1.2 10 0C2 1.2 1.2 2 0 10C-1.2 2-2 1.2-10 0C-2-1.2-1.2-2 0-10Z"
      fill="currentColor"
      stroke="none"
    />
  );
}

/** A disc whose lower-right edge is shaded with halftone, as if lit from the top left. */
export function ShadedDisc({ x, y, r, dots, fill = "#fff" }: { x: number; y: number; r: number; dots: string; fill?: string }) {
  const clip = useSvgId("fb-disc");
  return (
    <g>
      <clipPath id={clip}>
        <circle cx={x} cy={y} r={r} />
      </clipPath>
      <circle cx={x} cy={y} r={r} fill={fill} />
      <circle cx={x + r * 0.42} cy={y + r * 0.42} r={r} fill={dots} stroke="none" clipPath={`url(#${clip})`} />
      <circle cx={x} cy={y} r={r} />
    </g>
  );
}

/** The ₹ coin: BrandMark's rupee on a sunflower face. */
export function RupeeCoin({ x, y, r, dots }: { x: number; y: number; r: number; dots: string }) {
  const scale = (r * 0.9) / 18; // the rupee path is 18 units tall, centred on (12, 12)
  return (
    <g>
      <ShadedDisc x={x} y={y} r={r} dots={dots} />
      <circle cx={x} cy={y} r={r * 0.72} fill={SUNFLOWER} strokeWidth={2} />
      <path
        transform={`translate(${x - 12 * scale} ${y - 12 * scale}) scale(${scale})`}
        d="M6 3h12M6 8h12M6 13h3M9 13c6.667 0 6.667-10 0-10M6 13l8.5 8"
        strokeWidth={3 / scale}
      />
    </g>
  );
}
