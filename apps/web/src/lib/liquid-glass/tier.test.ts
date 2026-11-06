import assert from "node:assert/strict";
import { test } from "node:test";
import { chooseTier, frameTimeP90, isGlassLook, isGlassTier, type GlassCapabilities } from "./tier.ts";

const chrome: GlassCapabilities = {
  chromium: true,
  backdropFilter: true,
  reducedTransparency: false,
  moreContrast: false,
  forcedColors: false,
  deviceMemory: 8,
  janky: false,
  override: null,
};

test("Chromium refracts; Safari and Firefox get frosted glass", () => {
  assert.equal(chooseTier(chrome), "refract");
  assert.equal(chooseTier({ ...chrome, chromium: false }), "frost");
  assert.equal(chooseTier({ ...chrome, deviceMemory: undefined }), "refract");
});

test("accessibility settings and missing backdrop filters get solid glass", () => {
  for (const setting of ["reducedTransparency", "moreContrast", "forcedColors"] as const) {
    assert.equal(chooseTier({ ...chrome, [setting]: true }), "solid", setting);
    assert.equal(chooseTier({ ...chrome, [setting]: true, override: "refract" }), "solid", `${setting} beats an override`);
  }
  assert.equal(chooseTier({ ...chrome, backdropFilter: false }), "solid");
});

test("low memory and janky scrolling fall back to frost", () => {
  assert.equal(chooseTier({ ...chrome, deviceMemory: 2 }), "frost");
  assert.equal(chooseTier({ ...chrome, janky: true }), "frost");
});

test("the ?glass= override never forces refraction onto other engines", () => {
  assert.equal(chooseTier({ ...chrome, override: "frost" }), "frost");
  assert.equal(chooseTier({ ...chrome, override: "solid" }), "solid");
  assert.equal(chooseTier({ ...chrome, janky: true, override: "refract" }), "refract");
  assert.equal(chooseTier({ ...chrome, chromium: false, override: "refract" }), "frost");
  assert.equal(chooseTier({ ...chrome, override: "sparkly" }), "refract");
});

test("frame-time percentile and value guards", () => {
  assert.equal(frameTimeP90([]), 0);
  assert.equal(frameTimeP90([16, 16, 16, 16, 16, 16, 16, 16, 16, 40]), 40);
  // A few slow frames are tolerated; one in seven is not.
  assert.equal(frameTimeP90(Array.from({ length: 100 }, (_, index) => (index < 95 ? 16 : 50))), 16);
  assert.equal(frameTimeP90(Array.from({ length: 100 }, (_, index) => (index < 85 ? 16 : 50))), 50);
  assert.ok(isGlassTier("frost") && !isGlassTier("glass"));
  assert.ok(isGlassLook("tinted") && !isGlassLook("dark"));
});
