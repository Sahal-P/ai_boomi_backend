// Constants of three's NeutralToneMapping (Khronos PBR Neutral) at exposure 1.
const START = 0.8 - 0.04;
const DESATURATION = 0.15;
const D = 1 - START;

/**
 * GLSL `preToneMapped(target)`: the linear colour that Neutral tone mapping maps onto `target`
 * (linear in, linear out). Use it wherever a rendered colour must be identical to the CSS
 * background around it (bright backgrounds are otherwise compressed and read as a grey box).
 * Closed-form inverse; assumes every channel stays above the curve's toe, true for page tints.
 */
export const PRE_TONE_MAPPED_GLSL = /* glsl */ `
  vec3 preToneMapped(vec3 target) {
    float newPeak = max(target.r, max(target.g, target.b));
    if (newPeak < ${START.toFixed(2)}) return target + 0.04;
    float peak = ${(D * D).toFixed(4)} / (1.0 - newPeak) - ${D.toFixed(2)} + ${START.toFixed(2)};
    float mixing = 1.0 - 1.0 / (${DESATURATION.toFixed(2)} * (peak - newPeak) + 1.0);
    return (target - newPeak * mixing) / (1.0 - mixing) * (peak / newPeak) + 0.04;
  }
`;
