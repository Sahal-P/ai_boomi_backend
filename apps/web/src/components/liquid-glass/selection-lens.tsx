"use client";

import { animate, AnimatePresence, motion, useMotionValue, useReducedMotion, useTransform, useVelocity } from "motion/react";
import { useCallback, useRef, useState, type MouseEvent, type PointerEvent, type ReactNode } from "react";

import { useLiquidGlass } from "@/components/liquid-glass/use-liquid-glass";

type Drag = { pointerId: number; startX: number; active: boolean };

/** Pixels a press must travel before it becomes a drag (taps stay plain link clicks). */
const DRAG_START = 6;

/**
 * Apple's drag-to-select lens for a row of links (the phone tab bar, segmented controls). Press and
 * slide: a clear glass droplet follows the finger, magnifying what it passes (in Chromium) and
 * stretching with its speed; release over an item to choose it — through that link's own click, so
 * GuardedLink still asks before discarding unsaved work. Taps and the keyboard use the links
 * directly; the lens is decoration (aria-hidden).
 *
 * Render `lens` beside the container (in a positioned parent whose left edge is the container's),
 * never inside glass that has a backdrop filter: that glass would be the lens's backdrop root.
 */
export function useSelectionLens<T extends HTMLElement>({ itemSelector = "a" }: { itemSelector?: string } = {}) {
  const container = useRef<T | null>(null);
  const attach = useCallback((node: T | null) => {
    container.current = node;
  }, []);
  const drag = useRef<Drag | null>(null);
  const swallowClick = useRef(false);
  const [lens, setLens] = useState<{ width: number; height: number } | null>(null);
  const x = useMotionValue(0);
  const speed = useVelocity(x);
  const stretch = useTransform(speed, [-2400, 0, 2400], [1.22, 1, 1.22], { clamp: true });
  const squash = useTransform(speed, [-2400, 0, 2400], [0.88, 1, 0.88], { clamp: true });
  const reduce = useReducedMotion();
  /** Glide toward the finger on a gel spring (straight there under reduced motion). */
  const glide = (target: number) => {
    if (reduce) x.set(target);
    else animate(x, target, { type: "spring", stiffness: 650, damping: 40, mass: 0.6 });
  };
  const { attach: attachGlass, filter } = useLiquidGlass<HTMLSpanElement>({
    bezel: 10,
    thickness: 12,
    magnify: 1.28,
    dispersion: 1,
    enabled: lens !== null,
  });

  const items = () => [...(container.current?.querySelectorAll<HTMLElement>(itemSelector) ?? [])];
  const itemAt = (clientX: number) => {
    let closest: HTMLElement | undefined;
    let distance = Number.POSITIVE_INFINITY;
    for (const item of items()) {
      const box = item.getBoundingClientRect();
      const gap = clientX < box.left ? box.left - clientX : clientX > box.right ? clientX - box.right : 0;
      if (gap < distance) {
        closest = item;
        distance = gap;
      }
    }
    return closest;
  };
  const offset = (clientX: number, width: number) => {
    const bounds = container.current?.getBoundingClientRect();
    if (!bounds) return 0;
    return Math.min(Math.max(clientX - bounds.left - width / 2, 0), bounds.width - width);
  };

  const finish = () => {
    drag.current = null;
    setLens(null);
  };

  const handlers = {
    onPointerDown(event: PointerEvent<T>) {
      if (event.button !== 0 || !event.isPrimary) return;
      drag.current = { pointerId: event.pointerId, startX: event.clientX, active: false };
    },
    onPointerMove(event: PointerEvent<T>) {
      const current = drag.current;
      const node = container.current;
      if (!current || current.pointerId !== event.pointerId || !node) return;
      if (!current.active) {
        if (Math.abs(event.clientX - current.startX) < DRAG_START) return;
        current.active = true;
        try {
          node.setPointerCapture(event.pointerId);
        } catch {
          // Without capture the lens still follows while the finger stays over the bar.
        }
        const pressed = itemAt(current.startX)?.getBoundingClientRect();
        const width = (pressed?.width ?? 64) + 14;
        const height = node.getBoundingClientRect().height + 10;
        setLens({ width, height });
        x.jump(offset(current.startX, width));
      }
      glide(offset(event.clientX, lens?.width ?? (itemAt(event.clientX)?.getBoundingClientRect().width ?? 64) + 14));
    },
    onPointerUp(event: PointerEvent<T>) {
      const current = drag.current;
      if (!current || current.pointerId !== event.pointerId) return;
      if (!current.active) {
        drag.current = null;
        return; // A tap: the link's own click navigates.
      }
      const target = itemAt(event.clientX);
      finish();
      target?.click();
      // The browser may still deliver the drag's own click; the choice above already counted.
      swallowClick.current = true;
      window.setTimeout(() => {
        swallowClick.current = false;
      }, 400);
    },
    onPointerCancel: finish,
    onLostPointerCapture: () => {
      if (drag.current?.active) finish();
    },
    onClickCapture(event: MouseEvent<T>) {
      if (!swallowClick.current || !event.isTrusted) return;
      swallowClick.current = false;
      event.preventDefault();
      event.stopPropagation();
    },
  };

  const element: ReactNode = (
    <AnimatePresence>
      {lens ? (
        <motion.span
          key="lens"
          ref={attachGlass}
          aria-hidden="true"
          data-selection-lens=""
          className="lg lg-lens pointer-events-none absolute left-0 z-10 rounded-full"
          style={{
            width: lens.width,
            height: lens.height,
            top: -5,
            x,
            scaleX: reduce ? 1 : stretch,
            scaleY: reduce ? 1 : squash,
          }}
          initial={{ opacity: 0, scale: 0.7 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.86, transition: { duration: 0.18 } }}
          transition={{ type: "spring", stiffness: 520, damping: 30 }}
        >
          {filter}
        </motion.span>
      ) : null}
    </AnimatePresence>
  );

  return { attach, handlers, lens: element };
}
