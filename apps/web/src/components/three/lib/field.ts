import { useFrame } from "@react-three/fiber";
import { useMemo, type RefObject } from "react";
import * as THREE from "three";

import { PRE_TONE_MAPPED_GLSL } from "./tone";

/**
 * The page's glass field (`.bg-field` in globals.css) recomputed per fragment. The field is fixed
 * to the viewport, so what sits behind a scene changes as the page scrolls; a scene that needs
 * something opaque behind it (glass refracts its backdrop) paints `fieldBehind()` instead of a
 * flat colour and stays seamless at every scroll position, glows included. Mirrors
 * `.bg-field::before` and the grain's average (`::after`): keep the two in step.
 *
 * The vertex shader must declare `varying vec4 vClip;` and set `vClip = gl_Position;`.
 */
export const FIELD_GLSL = /* glsl */ `
  uniform vec4 uSlot;
  uniform vec2 uScreen;
  uniform vec3 uField;
  uniform vec3 uFieldCool;
  uniform vec3 uFieldWarm;
  uniform vec3 uGlows;
  varying vec4 vClip;
  ${PRE_TONE_MAPPED_GLSL}

  float fieldGlow(vec2 uv, vec2 centre, vec2 radii, float stop) {
    return clamp(1.0 - length((uv - centre) / radii) / stop, 0.0, 1.0);
  }

  vec3 srgbToLinear(vec3 color) {
    return mix(color / 12.92, pow((color + 0.055) / 1.055, vec3(2.4)), step(0.04045, color));
  }

  // The field under this fragment, as the linear colour that tone-maps onto the CSS pixel.
  vec3 fieldBehind() {
    vec2 ndc = vClip.xy / vClip.w;
    vec2 uv = (uSlot.xy + vec2(0.5 + 0.5 * ndc.x, 0.5 - 0.5 * ndc.y) * uSlot.zw) / uScreen;
    // CSS composites the layers in gamma-encoded sRGB, bottom first.
    vec3 color = uField;
    color = mix(color, vec3(1.0), 0.55 * uGlows.x * fieldGlow(uv, vec2(0.18, 0.0), vec2(0.8, 0.45), 0.7));
    color = mix(color, uFieldWarm, uGlows.y * fieldGlow(uv, vec2(1.0, 0.56), vec2(0.9, 0.55), 0.66));
    color = mix(color, uFieldCool, uGlows.z * fieldGlow(uv, vec2(0.0, 1.0), vec2(1.2, 0.62), 0.64));
    // The grain: ink noise at 3% opacity, half covered on average.
    color = mix(color, vec3(0.05, 0.06, 0.08), 0.015);
    return preToneMapped(srgbToLinear(color));
  }
`;

/** A CSS colour token as gamma-encoded components, the space CSS composites in. */
function token(style: CSSStyleDeclaration, name: string): THREE.Color {
  return new THREE.Color(style.getPropertyValue(name).trim()).convertLinearToSRGB();
}

/**
 * Uniforms for FIELD_GLSL, updated from the slot element every frame before its view renders.
 * Colours come from the CSS tokens, so globals.css stays their one source.
 */
export function useFieldUniforms(track: RefObject<HTMLElement | null>) {
  const uniforms = useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    return {
      uSlot: { value: new THREE.Vector4(0, 0, 1, 1) },
      uScreen: { value: new THREE.Vector2(1, 1) },
      uField: { value: token(style, "--field") },
      uFieldCool: { value: token(style, "--field-cool") },
      uFieldWarm: { value: token(style, "--field-warm") },
      // Strength of the white highlight, the warm and the cool glow.
      uGlows: { value: new THREE.Vector3(1, 1, 1) },
    };
  }, []);
  // Reduce Transparency flattens the field to its base colour (globals.css).
  const flat = useMemo(() => window.matchMedia("(prefers-reduced-transparency: reduce)"), []);

  useFrame(({ gl }) => {
    const slot = track.current?.getBoundingClientRect();
    if (!slot) return;
    const screen = gl.domElement.getBoundingClientRect();
    uniforms.uSlot.value.set(slot.left - screen.left, slot.top - screen.top, slot.width, slot.height);
    uniforms.uScreen.value.set(screen.width, screen.height);
    uniforms.uGlows.value.setScalar(flat.matches ? 0 : 1);
  });

  return uniforms;
}
