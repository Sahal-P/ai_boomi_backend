import assert from "node:assert/strict";
import { test } from "node:test";
import { acceptsScreenshot, base64Of, fitted } from "./screenshot.ts";

test("screenshots shrink to fit and never grow", () => {
  assert.deepEqual(fitted(1170, 2532), { width: 1170, height: 2532 });
  assert.deepEqual(fitted(3200, 1800), { width: 1600, height: 900 });
  assert.deepEqual(fitted(1000, 10_000), { width: 400, height: 4000 });
  assert.deepEqual(fitted(5000, 1), { width: 1600, height: 1 });
});

test("only PNG, JPEG and WebP pictures are opened", () => {
  for (const type of ["image/png", "image/jpeg", "image/webp"]) assert.ok(acceptsScreenshot(type), type);
  for (const type of ["image/gif", "image/svg+xml", "image/heic", "application/pdf", ""]) {
    assert.ok(!acceptsScreenshot(type), type);
  }
});

test("the base64 part of a data URL is sent without its prefix", () => {
  assert.equal(base64Of("data:image/webp;base64,UklGRg=="), "UklGRg==");
  assert.equal(base64Of("not a data url"), "");
});
