import { useSyncExternalStore } from "react";

let supported: boolean | null = null;
let renderer = "";

/** Cached capability probe; the probe context is released immediately. */
function probeWebGL(): boolean {
  if (supported !== null) return supported;
  try {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    supported = Boolean(context);
    const info = context?.getExtension("WEBGL_debug_renderer_info");
    if (context && info) renderer = String(context.getParameter(info.UNMASKED_RENDERER_WEBGL));
    context?.getExtension("WEBGL_lose_context")?.loseContext();
  } catch {
    supported = false;
  }
  return supported;
}

const noop = () => () => {};

/** False during SSR and when the browser cannot create a WebGL context. */
export function useWebGLSupport(): boolean {
  return useSyncExternalStore(noop, probeWebGL, () => false);
}

export function supportsWebGL(): boolean {
  return probeWebGL();
}

/** GPU renderer string when the browser exposes it ("" otherwise); used for tier hints only. */
export function webglRenderer(): string {
  probeWebGL();
  return renderer;
}
