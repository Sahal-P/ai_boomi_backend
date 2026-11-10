import assert from "node:assert/strict";
import { test } from "node:test";
import { boldSegments } from "./bold-text.ts";

test("WhatsApp-style bold becomes bold runs without its asterisks", () => {
  assert.deepEqual(boldSegments("You spent *₹4,200* on food."), [
    { text: "You spent ", bold: false },
    { text: "₹4,200", bold: true },
    { text: " on food.", bold: false },
  ]);
  assert.deepEqual(boldSegments("खाने पर *₹420* खर्च हुए"), [
    { text: "खाने पर ", bold: false },
    { text: "₹420", bold: true },
    { text: " खर्च हुए", bold: false },
  ]);
  assert.deepEqual(boldSegments("*Tip:* keep a list"), [
    { text: "Tip:", bold: true },
    { text: " keep a list", bold: false },
  ]);
});

test("asterisks that are not bold markers stay as they are", () => {
  for (const text of ["2*3*4", "a * b * c", "**", "*unclosed", "", "Plain answer"]) {
    const segments = boldSegments(text);
    assert.equal(segments.map((part) => part.text).join(""), text, text);
    assert.ok(segments.every((part) => !part.bold), text);
  }
});
