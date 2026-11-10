import assert from "node:assert/strict";
import { test } from "node:test";
import { progressLabel } from "./advisor-progress.ts";

test("each advisor step has plain words, and anything else reads as thinking", () => {
  assert.equal(progressLabel("category_spending"), "Looking at your spending…");
  assert.equal(progressLabel("search_knowledge"), "Reading FinBoy's money guides…");
  assert.equal(progressLabel("plan_numbers"), "Working out the numbers…");
  for (const stage of ["constructor", "toString", "unknown_tool", "", null, undefined]) {
    assert.equal(progressLabel(stage), "Thinking…");
  }
});
