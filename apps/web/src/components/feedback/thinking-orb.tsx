"use client";

import { useEffect, useState } from "react";
import { ThinkingOrb as DottedOrb, type OrbSize, type OrbState } from "thinking-orbs";

/**
 * FinBoy's AI at work: Jakub Antalik's dotted thinking orbs (MIT, 2D canvas — no WebGL). Use
 * them only where FinBoy's AI is doing something, or resting on Ask; data loading keeps the
 * plain spinner. Pinned to dark ink: FinBoy is light-only, and the library's `auto` theme would
 * draw light dots under a dark OS setting. 64 and 20 are the library's two tuned designs.
 */
export function ThinkingOrb({
  state,
  size = 64,
  label,
  rest = false,
  className,
}: {
  state: OrbState;
  size?: OrbSize;
  /** Name it only when no nearby text already says what FinBoy is doing. */
  label?: string;
  /** Decorative orbs settle after five seconds (WCAG 2.2.2); task orbs move while the task runs. */
  rest?: boolean;
  className?: string;
}) {
  const [resting, setResting] = useState(false);
  useEffect(() => {
    if (!rest) return;
    const timer = window.setTimeout(() => setResting(true), 5_000);
    return () => window.clearTimeout(timer);
  }, [rest]);
  return (
    <DottedOrb
      state={state}
      size={size}
      theme="light"
      paused={rest && resting}
      data-thinking-orb={state}
      className={className}
      {...(label ? { "aria-label": label } : { "aria-hidden": true })}
    />
  );
}
