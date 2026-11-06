"use client";

import { useEffect } from "react";

import { glassStore } from "@/components/liquid-glass/glass-store";
import { chooseTier, frameTimeP90, JANK_FRAME_MS, type GlassCapabilities } from "@/lib/liquid-glass/tier";

const OVERRIDE_KEY = "finboy.glass-override";
const JANK_KEY = "finboy.glass-janky";
/** What flexes and lights up when pressed: opted-in elements and glass links and buttons. */
const GLASS_PRESSABLE =
  "[data-glass-press], :is(a, button):is(.lg-prominent, .lg-static, .lg-on-color)";

type Navigation = Navigator & {
  userAgentData?: { brands?: { brand: string }[] };
  deviceMemory?: number;
};

function session(key: string, value?: string | null): string | null {
  try {
    if (value === undefined) return sessionStorage.getItem(key);
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch {
    // Storage can be refused; the default tier still applies.
  }
  return value ?? null;
}

/**
 * Picks the glass tier after hydration (server HTML is always `frost`), keeps it in step with
 * Reduce Transparency, Increase Contrast and forced colours, drops refraction for the session if
 * scrolling stays janky, and lights glass up from the point where it is pressed. Renders nothing.
 */
export function GlassProvider() {
  useEffect(() => {
    const root = document.documentElement;
    const navigation = navigator as Navigation;
    const queries = {
      reducedTransparency: matchMedia("(prefers-reduced-transparency: reduce)"),
      moreContrast: matchMedia("(prefers-contrast: more)"),
      forcedColors: matchMedia("(forced-colors: active)"),
    };
    // QA: ?glass=refract|frost|solid holds for the tab's session; ?glass=auto clears it.
    const requested = new URLSearchParams(location.search).get("glass");
    if (requested) session(OVERRIDE_KEY, requested === "auto" ? null : requested);

    const capabilities = (): GlassCapabilities => ({
      chromium: Boolean(navigation.userAgentData?.brands?.some((entry) => entry.brand === "Chromium")),
      backdropFilter: CSS.supports("backdrop-filter", "blur(1px)") || CSS.supports("-webkit-backdrop-filter", "blur(1px)"),
      reducedTransparency: queries.reducedTransparency.matches,
      moreContrast: queries.moreContrast.matches,
      forcedColors: queries.forcedColors.matches,
      deviceMemory: navigation.deviceMemory,
      janky: session(JANK_KEY) === "1",
      override: session(OVERRIDE_KEY),
    });
    const apply = () => {
      const tier = chooseTier(capabilities());
      root.dataset.glassTier = tier;
      glassStore.setTier(tier);
    };
    apply();
    for (const query of Object.values(queries)) query.addEventListener("change", apply);

    // Jank guard: sample frame times only while the page scrolls with refraction on.
    const started = performance.now();
    let frames: number[] = [];
    let lastScroll = 0;
    let lastFrame = 0;
    let sampling = false;
    const tick = (now: number) => {
      if (lastFrame) frames.push(now - lastFrame);
      lastFrame = now;
      if (frames.length >= 60) {
        if (frameTimeP90(frames) > JANK_FRAME_MS && glassStore.tier() === "refract") {
          session(JANK_KEY, "1");
          apply();
        }
        frames = [];
      }
      if (now - lastScroll < 200 && document.visibilityState === "visible") {
        requestAnimationFrame(tick);
      } else {
        sampling = false;
        lastFrame = 0;
      }
    };
    const onScroll = () => {
      lastScroll = performance.now();
      if (sampling || glassStore.tier() !== "refract" || lastScroll - started < 1500) return;
      sampling = true;
      requestAnimationFrame(tick);
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    // Interactive illumination: the glow starts under the finger (Apple's "lights up from within").
    let pressed: HTMLElement | null = null;
    const release = () => {
      if (pressed) delete pressed.dataset.pressed;
      pressed = null;
    };
    const onPress = (event: PointerEvent) => {
      if (event.button !== 0 || !(event.target instanceof Element)) return;
      const target = event.target.closest(GLASS_PRESSABLE);
      if (!(target instanceof HTMLElement) || target.matches(":disabled, [aria-disabled='true']")) return;
      release();
      const box = target.getBoundingClientRect();
      target.style.setProperty("--lg-x", `${Math.round(event.clientX - box.left)}px`);
      target.style.setProperty("--lg-y", `${Math.round(event.clientY - box.top)}px`);
      target.dataset.pressed = "";
      pressed = target;
    };
    document.addEventListener("pointerdown", onPress, { capture: true, passive: true });
    for (const type of ["pointerup", "pointercancel", "dragstart"] as const) {
      document.addEventListener(type, release, { capture: true, passive: true });
    }
    window.addEventListener("blur", release);

    return () => {
      for (const query of Object.values(queries)) query.removeEventListener("change", apply);
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("pointerdown", onPress, { capture: true });
      for (const type of ["pointerup", "pointercancel", "dragstart"] as const) {
        document.removeEventListener(type, release, { capture: true });
      }
      window.removeEventListener("blur", release);
    };
  }, []);

  return null;
}
