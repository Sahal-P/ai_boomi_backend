import type { RefObject } from "react";

export type VoiceOrbState = "idle" | "listening" | "thinking" | "speaking";

/**
 * Every 3D illustration that can be placed in the page via <SceneSlot>.
 * Plain data (plus optional refs for live values) so slots can live in Server Components.
 */
export type SceneSpec =
  | {
      name: "coin-swirl";
      /** 0 = loose swirl, 1 = coins merged into one stack. */
      merge?: number;
      /** Continuously demo the merge (3 emails → 1 transaction). */
      loop?: boolean;
    }
  | { name: "check-orb" }
  | { name: "voice-orb"; state?: VoiceOrbState; /** Live 0–1 audio level (mic or speech). */ level?: RefObject<number> }
  | { name: "coin-stack"; /** Relative column heights, 0–1. */ values: readonly number[] }
  | { name: "privacy-vault" }
  | { name: "ribbon" }
  | { name: "inbox-slab" };

export type SceneName = SceneSpec["name"];
