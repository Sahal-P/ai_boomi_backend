import assert from "node:assert/strict";
import { test } from "node:test";
import { roundedBoxDistance, roundedBoxNormal, squircleHeight, squircleSlope } from "./sdf.ts";

test("the rounded box distance is negative inside, zero on the edge and positive outside", () => {
  // A 100 × 50 box with 10 px corners, centred on the origin.
  assert.equal(roundedBoxDistance(0, 0, 50, 25, 10), -25);
  assert.equal(roundedBoxDistance(50, 0, 50, 25, 10), 0);
  assert.equal(roundedBoxDistance(0, -25, 50, 25, 10), 0);
  assert.ok(roundedBoxDistance(60, 0, 50, 25, 10) > 0);
  // The square corner itself lies outside the rounded one.
  assert.ok(roundedBoxDistance(50, 25, 50, 25, 10) > 0);
  // On the corner arc: 10 px from the arc's centre at (40, 15).
  assert.ok(Math.abs(roundedBoxDistance(40 + 10 * Math.SQRT1_2, 15 + 10 * Math.SQRT1_2, 50, 25, 10)) < 1e-9);
});

test("normals face out of the nearest edge", () => {
  assert.deepEqual(roundedBoxNormal(45, 0, 50, 25, 10), { x: 1, y: 0 });
  assert.deepEqual(roundedBoxNormal(-45, 0, 50, 25, 10), { x: -1, y: 0 });
  assert.deepEqual(roundedBoxNormal(0, -20, 50, 25, 10), { x: 0, y: -1 });
  assert.deepEqual(roundedBoxNormal(0, 20, 50, 25, 10), { x: 0, y: 1 });
  const corner = roundedBoxNormal(47, 22, 50, 25, 10);
  assert.ok(corner.x > 0 && corner.y > 0);
  assert.ok(Math.abs(Math.hypot(corner.x, corner.y) - 1) < 1e-9);
});

test("the squircle bezel rises from the rim to a flat face", () => {
  assert.equal(squircleHeight(0), 0);
  assert.equal(squircleHeight(1), 1);
  let previous = -1;
  for (let t = 0; t <= 1; t += 0.05) {
    const height = squircleHeight(t);
    assert.ok(height >= previous);
    previous = height;
  }
  assert.equal(squircleSlope(1), 0);
  assert.ok(squircleSlope(0) > 100);
});
