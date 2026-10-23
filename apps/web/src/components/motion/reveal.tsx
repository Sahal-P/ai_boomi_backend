"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react";

export const EASE_OUT_EXPO = [0.22, 1, 0.36, 1] as const;

type RevealProps = HTMLMotionProps<"div"> & {
  delay?: number;
  /** Vertical travel in px before settling. */
  distance?: number;
};

/** Fades content up out of a soft blur the first time it scrolls into view. */
export function Reveal({ delay = 0, distance = 28, children, ...props }: RevealProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: distance, filter: "blur(10px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-12% 0px" }}
      transition={reduced ? { duration: 0 } : { duration: 1.1, ease: EASE_OUT_EXPO, delay }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
