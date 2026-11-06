import { useSyncExternalStore } from "react";

import { GLASS_LOOK_KEY } from "@/lib/liquid-glass/look";
import { isGlassLook, type GlassLook, type GlassTier } from "@/lib/liquid-glass/tier";

/**
 * The page's glass state: the rendering tier (chosen after hydration by GlassProvider) and the
 * person's Clear · Tinted look (set before first paint by the root layout's inline script, from
 * localStorage). Server renders always see `frost` and `clear`, so markup never branches on them.
 */
type State = { tier: GlassTier; look: GlassLook };

function initialLook(): GlassLook {
  if (typeof document === "undefined") return "clear";
  const look = document.documentElement.dataset.glassLook;
  return isGlassLook(look) ? look : "clear";
}

let state: State = { tier: "frost", look: initialLook() };
const listeners = new Set<() => void>();

function update(next: Partial<State>) {
  const merged = { ...state, ...next };
  if (merged.tier === state.tier && merged.look === state.look) return;
  state = merged;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const glassStore = {
  tier: () => state.tier,
  look: () => state.look,
  setTier: (tier: GlassTier) => update({ tier }),
  subscribe,
};

export function useGlassTier(): GlassTier {
  return useSyncExternalStore(subscribe, glassStore.tier, () => "frost");
}

export function useGlassLook(): GlassLook {
  return useSyncExternalStore(subscribe, glassStore.look, () => "clear");
}

/** Switches every glass surface at once and remembers the choice on this device. */
export function setGlassLook(look: GlassLook) {
  document.documentElement.dataset.glassLook = look;
  try {
    localStorage.setItem(GLASS_LOOK_KEY, look);
  } catch {
    // Private windows can refuse storage; the choice still applies until the page is closed.
  }
  update({ look });
}
