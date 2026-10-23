import * as THREE from "three";

import { createRandom } from "./random";

function canvasTexture(
  size: number,
  draw: (context: CanvasRenderingContext2D, size: number) => void,
): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("2D canvas is unavailable");
  draw(context, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

/** Writes a 0–1 grayscale field into a canvas texture (alpha = value when `asAlpha`). */
function fieldTexture(size: number, field: Float32Array, asAlpha = false): THREE.CanvasTexture {
  return canvasTexture(size, (context) => {
    const image = context.createImageData(size, size);
    for (let index = 0; index < field.length; index += 1) {
      const value = Math.round(Math.min(Math.max(field[index] ?? 0, 0), 1) * 255);
      image.data.set(asAlpha ? [255, 255, 255, value] : [value, value, value, 255], index * 4);
    }
    context.putImageData(image, 0, 0);
  });
}

/** Separable box blur, three passes ≈ Gaussian. Clamped edges. */
function blur(field: Float32Array, size: number, radius: number): void {
  const line = new Float32Array(size);
  for (let pass = 0; pass < 3; pass += 1) {
    for (const horizontal of [true, false]) {
      for (let a = 0; a < size; a += 1) {
        for (let b = 0; b < size; b += 1) line[b] = field[horizontal ? a * size + b : b * size + a] ?? 0;
        let sum = 0;
        for (let k = -radius; k <= radius; k += 1) sum += line[Math.min(Math.max(k, 0), size - 1)] ?? 0;
        for (let b = 0; b < size; b += 1) {
          field[horizontal ? a * size + b : b * size + a] = sum / (radius * 2 + 1);
          sum += (line[Math.min(b + radius + 1, size - 1)] ?? 0) - (line[Math.max(b - radius, 0)] ?? 0);
        }
      }
    }
  }
}

/** World units covered by one repeat of the floor texture: 2 × 2 tiles of 4 units. */
export const FLOOR_TEXTURE_SPAN = 8;

/**
 * Honed terrazzo: near-white with faint mottling, sparse violet/blue/graphite chips and
 * chamfered tile seams (a dark groove with a lit edge). Seamless and deterministic.
 */
export function createFloorTexture(size: number): THREE.CanvasTexture {
  const texture = canvasTexture(size, (context, s) => {
    const random = createRandom(7);
    const px = s / 2048;
    // Draws at every wrapped position the shape can reach, so the texture tiles seamlessly.
    const wrapped = (x: number, y: number, reach: number, draw: (x: number, y: number) => void) => {
      for (const dx of [-s, 0, s]) {
        for (const dy of [-s, 0, s]) {
          if (x + dx + reach >= 0 && x + dx - reach <= s && y + dy + reach >= 0 && y + dy - reach <= s) draw(x + dx, y + dy);
        }
      }
    };

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, s, s);

    for (let index = 0; index < 70; index += 1) {
      const x = random() * s;
      const y = random() * s;
      const radius = s * (0.06 + random() * 0.14);
      const tone = random() < 0.55 ? "232, 227, 247" : "255, 253, 250";
      wrapped(x, y, radius, (cx, cy) => {
        const gradient = context.createRadialGradient(cx, cy, 0, cx, cy, radius);
        gradient.addColorStop(0, `rgba(${tone}, 0.45)`);
        gradient.addColorStop(1, `rgba(${tone}, 0)`);
        context.fillStyle = gradient;
        context.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
      });
    }

    const palette: Array<[string, number]> = [
      ["109, 74, 255", 0.32],
      ["62, 123, 250", 0.15],
      ["214, 58, 249", 0.1],
      ["44, 36, 74", 0.25],
      ["176, 156, 255", 0.18],
    ];
    const chip = (count: number, minRadius: number, maxRadius: number, minAlpha: number) => {
      for (let index = 0; index < count; index += 1) {
        let pick = random();
        const color = palette.find(([, weight]) => (pick -= weight) <= 0)?.[0] ?? palette[0]?.[0] ?? "0, 0, 0";
        const radius = (minRadius + (maxRadius - minRadius) * random() ** 2) * px;
        const squash = 0.45 + random() * 0.55;
        const angle = random() * Math.PI;
        const alpha = minAlpha + random() * (0.95 - minAlpha);
        const x = random() * s;
        const y = random() * s;
        wrapped(x, y, radius, (cx, cy) => {
          context.fillStyle = `rgba(${color}, ${alpha.toFixed(3)})`;
          context.beginPath();
          context.ellipse(cx, cy, radius, radius * squash, angle, 0, Math.PI * 2);
          context.fill();
        });
      }
    };
    chip(Math.round(900 * px * px), 1, 2, 0.2); // dust
    chip(Math.round(260 * px * px), 2, 5.5, 0.5); // chips

    // Seams on the tile edges (texture edge and centre): groove plus a catch-light lip.
    for (const at of [0, s / 2, s]) {
      context.fillStyle = "rgba(108, 92, 170, 0.2)";
      context.fillRect(at - 2.5 * px, 0, 5 * px, s);
      context.fillRect(0, at - 2.5 * px, s, 5 * px);
      context.fillStyle = "rgba(255, 255, 255, 0.95)";
      context.fillRect(at + 2.5 * px, 0, 1.5 * px, s);
      context.fillRect(0, at + 2.5 * px, s, 1.5 * px);
    }
  });
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  return texture;
}

/**
 * Window light for the sun spotlight's `map`: three tall panes with soft, blurred edges and
 * a falloff toward the cone rim, so the floor reads as lit through a large studio window.
 */
export function createWindowGoboTexture(): THREE.CanvasTexture {
  const size = 256;
  const field = new Float32Array(size * size);
  const panes: Array<[number, number]> = [
    [0.06, 0.24],
    [0.3, 0.48],
    [0.54, 0.72],
    [0.78, 0.96],
  ];
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const u = (x + 0.5) / size;
      const v = (y + 0.5) / size;
      const inPane = panes.some(([from, to]) => u >= from && u <= to) && v >= 0.04 && v <= 0.96;
      field[y * size + x] = inPane ? 1 : 0.015;
    }
  }
  blur(field, size, 7);
  const texture = fieldTexture(size, field);
  texture.anisotropy = 1;
  return texture;
}
