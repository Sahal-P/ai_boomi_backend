import assert from "node:assert/strict";
import { test } from "node:test";
import { sourceLabel, span } from "./signup-sources.ts";

test("median times read as minutes, hours or days", () => {
  assert.equal(span(null), "—");
  assert.equal(span(4.54), "4.5 min");
  assert.equal(span(83), "1 h 23 min");
  assert.equal(span(60 * 50), "2 d 2 h");
});

test("a source row names its tags, or why it has none", () => {
  assert.equal(sourceLabel({ source: "instagram", medium: "paid_social", campaign: "2026-11-ml-reel", direct: false }), "instagram · paid_social · 2026-11-ml-reel");
  assert.equal(sourceLabel({ source: "ig", medium: "social", campaign: null, direct: false }), "ig · social");
  assert.equal(sourceLabel({ source: null, medium: null, campaign: null, direct: false }), "No tags");
  assert.equal(sourceLabel({ source: null, medium: null, campaign: null, direct: true }), "No visit (shared number, QR code or an old link)");
});
