import * as THREE from "three";

// Constants of three's NeutralToneMapping (Khronos PBR Neutral) at exposure 1.
const START = 0.8 - 0.04;
const DESATURATION = 0.15;
const D = 1 - START;

/**
 * The linear colour that Neutral tone mapping maps onto `css`. Use it for a composer-rendered
 * scene's clear colour and fog so the canvas edge is identical to the CSS background around it
 * (bright backgrounds are otherwise compressed and the canvas reads as a grey box).
 * Closed-form inverse; assumes every channel stays above the curve's toe, true for page tints.
 */
export function preToneMapped(css: THREE.ColorRepresentation): THREE.Color {
  const target = new THREE.Color(css);
  const channels = [target.r, target.g, target.b];
  const newPeak = Math.max(...channels);
  if (newPeak < START) return target.addScalar(0.04);
  const peak = (D * D) / (1 - newPeak) - D + START;
  const mix = 1 - 1 / (DESATURATION * (peak - newPeak) + 1);
  const [r = 0, g = 0, b = 0] = channels.map((value) => ((value - newPeak * mix) / (1 - mix)) * (peak / newPeak) + 0.04);
  return new THREE.Color(r, g, b);
}
