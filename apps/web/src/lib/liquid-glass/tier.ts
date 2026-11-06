/**
 * Which Liquid Glass rendering a browser gets.
 *
 * - `refract`: real refraction, an SVG displacement filter inside `backdrop-filter`. Only Chromium
 *   paints `url()` there; Safari and Firefox drop the whole declaration, blur included, so the
 *   filter is attached only once Chromium is confirmed.
 * - `frost`: blur, saturation and brightness with the same rims, highlights and motion.
 * - `solid`: near-opaque glass for Reduce Transparency, Increase Contrast, forced colours and
 *   browsers without `backdrop-filter`.
 */
export type GlassTier = "refract" | "frost" | "solid";

export type GlassLook = "clear" | "tinted";

export type GlassCapabilities = {
  /** A Chromium engine (navigator.userAgentData lists "Chromium"). */
  chromium: boolean;
  backdropFilter: boolean;
  reducedTransparency: boolean;
  moreContrast: boolean;
  forcedColors: boolean;
  /** navigator.deviceMemory in GB where the browser reports it. */
  deviceMemory: number | undefined;
  /** Scrolling stayed janky with refraction on, earlier in this session. */
  janky: boolean;
  /** QA override from `?glass=`. */
  override: string | null;
};

export const GLASS_TIERS: readonly GlassTier[] = ["refract", "frost", "solid"];

export function isGlassTier(value: unknown): value is GlassTier {
  return typeof value === "string" && (GLASS_TIERS as readonly string[]).includes(value);
}

export function isGlassLook(value: unknown): value is GlassLook {
  return value === "clear" || value === "tinted";
}

export function chooseTier(capabilities: GlassCapabilities): GlassTier {
  const { override } = capabilities;
  if (override === "solid") return "solid";
  const accessible =
    capabilities.backdropFilter &&
    !capabilities.reducedTransparency &&
    !capabilities.moreContrast &&
    !capabilities.forcedColors;
  if (!accessible) return "solid";
  if (override === "frost") return "frost";
  // Refraction can never be forced onto an engine that would drop the whole backdrop filter.
  if (!capabilities.chromium) return "frost";
  if (override === "refract") return "refract";
  if (capabilities.janky) return "frost";
  if (capabilities.deviceMemory !== undefined && capabilities.deviceMemory < 4) return "frost";
  return "refract";
}

/** 90th-percentile frame time (ms) of a window of frames; the jank guard compares it to 22 ms. */
export function frameTimeP90(frames: readonly number[]): number {
  if (!frames.length) return 0;
  const sorted = [...frames].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.9))] ?? 0;
}

export const JANK_FRAME_MS = 22;
