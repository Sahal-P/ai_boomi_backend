"use client";

import { animate, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function formatRupees(amountMinor: number): string {
  return rupees.format(amountMinor / 100);
}

type AnimatedAmountProps = {
  /** Amount in paise, as every FinBoy API returns it. */
  amountMinor: number;
  className?: string;
  duration?: number;
  prefix?: string;
};

/**
 * Counts up to an INR amount when it enters the view. Text is written straight to the
 * DOM node (no re-render per frame); the final value is server-rendered for SEO and a11y.
 */
export function AnimatedAmount({ amountMinor, className, duration = 1.6, prefix = "" }: AnimatedAmountProps) {
  const node = useRef<HTMLSpanElement>(null);
  const inView = useInView(node, { once: true, margin: "-10% 0px" });
  const reduced = useReducedMotion();

  useEffect(() => {
    const element = node.current;
    if (!element || !inView || reduced) return;
    const controls = animate(0, amountMinor, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (value) => {
        element.textContent = prefix + formatRupees(Math.round(value / 100) * 100);
      },
    });
    return () => controls.stop();
  }, [amountMinor, duration, inView, prefix, reduced]);

  return (
    <span ref={node} className={cn("tabular", className)}>
      {prefix + formatRupees(amountMinor)}
    </span>
  );
}
