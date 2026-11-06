import { roundedBoxDistance, roundedBoxNormal, squircleHeight, squircleSlope } from "./sdf.ts";

/**
 * Displacement maps for Liquid Glass refraction (an `feDisplacementMap` inside `backdrop-filter`).
 *
 * A ray looking straight down through the glass bends at the curved bezel (Snell's law) and lands
 * on the content beneath, displaced toward the thicker centre. Each map pixel stores that offset:
 * red = x, green = y, 128 = none. Offsets always point inward, so sampling never leaves the
 * element (the backdrop outside it is not available to the filter). The flat face is neutral unless
 * the glass magnifies, as a lens does while dragged.
 */

export type GlassOptics = {
  /** Width of the curved bezel, in CSS px. */
  bezel: number;
  /** Height of the glass at its flat face, in CSS px (how strongly the rim bends light). */
  thickness: number;
  /** Index of refraction; glass is about 1.5. */
  ior: number;
  /** Magnification of the face, as a lens (1 = none). */
  magnify?: number;
};

export type MapRequest = GlassOptics & {
  /** Element size and corner radius in CSS px. */
  width: number;
  height: number;
  radius: number;
  /** Map pixels per CSS pixel; big panels use less and the image is stretched back. */
  resolution?: number;
};

export type DisplacementMap = {
  /** Map size in map pixels. */
  width: number;
  height: number;
  /** RGBA bytes: red and green carry the x and y offsets around 128. */
  data: Uint8ClampedArray;
  /** The `feDisplacementMap` scale (CSS px) that turns the encoded values back into offsets. */
  scale: number;
};

const NEUTRAL = 128;

/** Inward refraction shift (CSS px) at `depth` px inside the rim. */
export function bezelShift(depth: number, { bezel, thickness, ior }: GlassOptics): number {
  if (depth <= 0 || depth >= bezel || bezel <= 0) return 0;
  const t = depth / bezel;
  const incidence = Math.atan(squircleSlope(t) * (thickness / bezel));
  const refracted = Math.asin(Math.sin(incidence) / ior);
  return thickness * squircleHeight(t) * Math.tan(incidence - refracted);
}

/** Size, in map pixels, of the map for a request (at least 1×1). */
export function mapSize(request: Pick<MapRequest, "width" | "height" | "resolution">) {
  const resolution = request.resolution ?? 1;
  return {
    width: Math.max(1, Math.round(request.width * resolution)),
    height: Math.max(1, Math.round(request.height * resolution)),
  };
}

export function displacementMap(request: MapRequest): DisplacementMap {
  const { width, height } = mapSize(request);
  const resolution = width / Math.max(request.width, 1);
  const hx = request.width / 2;
  const hy = request.height / 2;
  const radius = Math.min(Math.max(request.radius, 0), hx, hy);
  const bezel = Math.max(0, Math.min(request.bezel, hx, hy));
  const optics: GlassOptics = { ...request, bezel };
  const lens = 1 - 1 / Math.max(request.magnify ?? 1, 1);

  const offsets = new Float32Array(width * height * 2);
  let largest = 0;
  for (let my = 0; my < height; my += 1) {
    const y = (my + 0.5) / resolution - hy;
    for (let mx = 0; mx < width; mx += 1) {
      const x = (mx + 0.5) / resolution - hx;
      const distance = roundedBoxDistance(x, y, hx, hy, radius);
      if (distance >= 0) continue;
      const shift = bezelShift(-distance, optics);
      const normal = roundedBoxNormal(x, y, hx, hy, radius);
      // Inward along the edge's normal, plus a pull toward the centre when magnifying.
      const ox = -normal.x * shift - x * lens;
      const oy = -normal.y * shift - y * lens;
      const index = (my * width + mx) * 2;
      offsets[index] = ox;
      offsets[index + 1] = oy;
      largest = Math.max(largest, Math.abs(ox), Math.abs(oy));
    }
  }

  const data = new Uint8ClampedArray(width * height * 4);
  for (let pixel = 0; pixel < width * height; pixel += 1) {
    const ox = offsets[pixel * 2] ?? 0;
    const oy = offsets[pixel * 2 + 1] ?? 0;
    data[pixel * 4] = largest ? NEUTRAL + Math.round((127 * ox) / largest) : NEUTRAL;
    data[pixel * 4 + 1] = largest ? NEUTRAL + Math.round((127 * oy) / largest) : NEUTRAL;
    data[pixel * 4 + 2] = NEUTRAL;
    data[pixel * 4 + 3] = 255;
  }
  // feDisplacementMap offsets by scale × (value / 255 − 0.5); 255 then means +largest px.
  return { width, height, data, scale: largest * 2 };
}

/** A stable cache key for a request (rounded, so sub-pixel layout noise reuses the same map). */
export function mapKey(request: MapRequest): string {
  const r = (value: number | undefined) => Math.round((value ?? 0) * 10) / 10;
  return [r(request.width), r(request.height), r(request.radius), r(request.bezel), r(request.thickness), r(request.ior), r(request.magnify ?? 1), r(request.resolution ?? 1)].join(":");
}
