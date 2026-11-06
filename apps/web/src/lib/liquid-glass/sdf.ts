/**
 * Shape maths for Liquid Glass. Signed distance functions (Inigo Quilez's rounded box) give, for
 * every pixel, how far it is from the glass edge and which way the edge faces; the bezel profile
 * gives the glass height there. Pure and DOM-free so it runs in unit tests.
 */

export type Vector = { x: number; y: number };

/**
 * Signed distance from (px, py) to a rounded box centred on the origin with half-size (hx, hy)
 * and corner radius r: negative inside, zero on the edge, positive outside.
 */
export function roundedBoxDistance(px: number, py: number, hx: number, hy: number, r: number): number {
  const qx = Math.abs(px) - hx + r;
  const qy = Math.abs(py) - hy + r;
  return Math.min(Math.max(qx, qy), 0) + Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) - r;
}

/**
 * Unit gradient of the rounded box's distance field: the outward normal of the nearest edge
 * (straight sides, or the corner arc's radius). Analytic, so no finite-difference noise.
 */
export function roundedBoxNormal(px: number, py: number, hx: number, hy: number, r: number): Vector {
  const sx = px < 0 ? -1 : 1;
  const sy = py < 0 ? -1 : 1;
  const qx = Math.abs(px) - hx + r;
  const qy = Math.abs(py) - hy + r;
  if (qx > 0 && qy > 0) {
    const length = Math.hypot(qx, qy);
    return { x: (sx * qx) / length, y: (sy * qy) / length };
  }
  return qx > qy ? { x: sx, y: 0 } : { x: 0, y: sy };
}

/**
 * The convex squircle bezel Apple's glass appears to use: height 0 at the rim rising to 1 where the
 * flat face begins. `t` runs 0 (rim) → 1 (flat face). Softer than a circular dome, so the rim
 * stays thin when a shape is stretched into a capsule.
 */
export function squircleHeight(t: number): number {
  const clamped = Math.min(Math.max(t, 0), 1);
  return (1 - (1 - clamped) ** 4) ** 0.25;
}

/** d(height)/dt of the squircle bezel; vertical (infinite) at the rim, zero at the flat face. */
export function squircleSlope(t: number): number {
  const u = 1 - Math.min(Math.max(t, 1e-4), 1);
  const inner = 1 - u ** 4;
  return inner <= 0 ? Number.POSITIVE_INFINITY : u ** 3 * inner ** -0.75;
}
