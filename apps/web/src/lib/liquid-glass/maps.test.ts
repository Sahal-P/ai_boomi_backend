import assert from "node:assert/strict";
import { test } from "node:test";
import { bezelShift, displacementMap, mapKey, mapSize, type MapRequest } from "./maps.ts";

const pill: MapRequest = { width: 200, height: 60, radius: 30, bezel: 14, thickness: 16, ior: 1.5 };

function pixel(map: ReturnType<typeof displacementMap>, x: number, y: number) {
  const index = (y * map.width + x) * 4;
  return { r: map.data[index] ?? 0, g: map.data[index + 1] ?? 0, b: map.data[index + 2] ?? 0, a: map.data[index + 3] ?? 0 };
}

test("the flat face and everything outside the shape stay neutral", () => {
  const map = displacementMap(pill);
  assert.deepEqual(pixel(map, 100, 30), { r: 128, g: 128, b: 128, a: 255 });
  // The square corner is outside the capsule.
  assert.deepEqual(pixel(map, 0, 0), { r: 128, g: 128, b: 128, a: 255 });
});

test("the rim pulls content from further inside, on every side", () => {
  const map = displacementMap(pill);
  // The capsule's ends are at x = 0 and x = 199; its rims are the outer 14 px.
  const left = pixel(map, 3, 30);
  const right = pixel(map, 196, 30);
  const top = pixel(map, 100, 1);
  const bottom = pixel(map, 100, 58);
  assert.ok(left.r > 128, "left rim samples to the right");
  assert.ok(right.r < 128, "right rim samples to the left");
  assert.ok(top.g > 128, "top rim samples downward");
  assert.ok(bottom.g < 128, "bottom rim samples upward");
  // Mirror images: equal and opposite offsets.
  assert.ok(Math.abs(left.r - 128 - (128 - right.r)) <= 1);
  assert.ok(Math.abs(top.g - 128 - (128 - bottom.g)) <= 1);
});

test("refraction is strongest near the rim and gone at the flat face", () => {
  const optics = { bezel: 14, thickness: 16, ior: 1.5 };
  const samples = Array.from({ length: 140 }, (_, index) => bezelShift((index + 0.5) / 10, optics));
  const peak = samples.indexOf(Math.max(...samples));
  assert.ok(peak / 10 < 14 * 0.3, `peak at ${peak / 10} px should sit in the outer third of the bezel`);
  assert.equal(bezelShift(14, optics), 0);
  assert.equal(bezelShift(20, optics), 0);
  assert.equal(bezelShift(0, optics), 0);
});

test("the scale turns the encoded byte range back into the largest offset", () => {
  const map = displacementMap(pill);
  let largest = 0;
  for (let index = 0; index < map.width * map.height; index += 1) {
    largest = Math.max(largest, Math.abs((map.data[index * 4] ?? 128) - 128), Math.abs((map.data[index * 4 + 1] ?? 128) - 128));
  }
  assert.equal(largest, 127);
  const strongest = Math.max(...Array.from({ length: 1400 }, (_, index) => bezelShift((index + 0.5) / 100, pill)));
  // Within one map pixel's sampling of the profile.
  assert.ok(map.scale / 2 <= strongest + 1e-9 && map.scale / 2 > strongest * 0.8);
});

test("a lens magnifies its face by pulling samples toward the centre", () => {
  const lens = displacementMap({ ...pill, magnify: 1.25 });
  const centre = pixel(lens, 100, 30);
  assert.ok(Math.abs(centre.r - 128) <= 1 && Math.abs(centre.g - 128) <= 1);
  assert.ok(pixel(lens, 60, 30).r > 128, "left of centre samples toward the centre");
  assert.ok(pixel(lens, 140, 30).r < 128, "right of centre samples toward the centre");
});

test("big panels can use a coarser map", () => {
  assert.deepEqual(mapSize({ width: 400, height: 700, resolution: 0.5 }), { width: 200, height: 350 });
  const coarse = displacementMap({ ...pill, resolution: 0.5 });
  assert.equal(coarse.width, 100);
  assert.equal(coarse.data.length, 100 * 30 * 4);
  assert.ok(Math.abs(coarse.scale - displacementMap(pill).scale) < 2);
});

test("cache keys ignore sub-pixel layout noise", () => {
  assert.equal(mapKey({ ...pill, width: 200.01 }), mapKey(pill));
  assert.notEqual(mapKey({ ...pill, width: 201 }), mapKey(pill));
});
