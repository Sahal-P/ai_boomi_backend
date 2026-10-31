"use client";

import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";

/** App screens follow the OS "reduce motion" setting for every motion animation, springs and
 *  layout moves included, without branching what is rendered. */
export function AppMotion({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
