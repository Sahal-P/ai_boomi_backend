import type { CSSProperties, HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const EASE_OUT_EXPO = [0.22, 1, 0.36, 1] as const;

type RevealProps = HTMLAttributes<HTMLDivElement> & {
  /** Stagger in seconds, as before: it now moves where in the scroll the rise happens. */
  delay?: number;
  /** Vertical travel in px before settling. */
  distance?: number;
};

/**
 * Rises content into place as it scrolls into view, in CSS alone (`.reveal` in globals.css).
 * The server HTML is already visible, so nothing waits for JavaScript on a slow phone; browsers
 * without view timelines, and reduced motion, simply show it.
 */
export function Reveal({ delay = 0, distance = 28, className, style, ...props }: RevealProps) {
  const timing = {
    "--reveal-distance": `${distance}px`,
    "--reveal-stagger": `${Math.round(delay * 40)}%`,
  } as CSSProperties;
  return <div className={cn("reveal", className)} style={{ ...timing, ...style }} {...props} />;
}
