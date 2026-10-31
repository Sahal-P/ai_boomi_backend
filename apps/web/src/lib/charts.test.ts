import assert from "node:assert/strict";
import { test } from "node:test";
import { compactMoney, daysCounted, donutArcs, foldSlices, niceTicks, sharePercent } from "./charts.ts";

const row = (category: Parameters<typeof foldSlices>[0][number]["category"], amount_minor: number) => ({
  category,
  amount_minor,
  transaction_count: 1,
});

test("the donut keeps five categories and folds the rest, never a tail of one", () => {
  const seven = [
    row("food_dining", 700),
    row("groceries", 600),
    row("transport", 500),
    row("rent", 400),
    row("health", 300),
    row("shopping", 200),
    row("education", 100),
  ];
  const folded = foldSlices(seven);
  assert.deepEqual(
    folded.slices.map((slice) => [slice.key, slice.amount_minor]),
    [["food_dining", 700], ["groceries", 600], ["transport", 500], ["rent", 400], ["health", 300], ["rest", 300]],
  );
  assert.equal(folded.total_minor, 2800);
  assert.equal(folded.slices.reduce((sum, slice) => sum + slice.share, 0), 1);
  // Six categories fit as they are: folding one into "rest" would only hide its name.
  assert.equal(foldSlices(seven.slice(0, 6)).slices.length, 6);
  assert.ok(foldSlices(seven.slice(0, 6)).slices.every((slice) => slice.key !== "rest"));
});

test("net refunds stay out of the drawing, and an empty month has no slices", () => {
  const folded = foldSlices([row("shopping", -500), row("food_dining", 1000)]);
  assert.deepEqual(folded.slices.map((slice) => slice.key), ["food_dining"]);
  assert.deepEqual(folded.refunds.map((refund) => refund.category), ["shopping"]);
  assert.deepEqual(foldSlices([row("shopping", -500)]).slices, []);
});

test("arcs leave a gap between neighbours and a lone slice is the whole ring", () => {
  assert.deepEqual(donutArcs([1], 0.01), [{ start: 0, length: 1 }]);
  const arcs = donutArcs([0.5, 0.3, 0.2], 0.01);
  assert.deepEqual(arcs.map((arc) => arc.start), [0, 0.5, 0.8]);
  assert.deepEqual(arcs.map((arc) => Number(arc.length.toFixed(2))), [0.49, 0.29, 0.19]);
  // A sliver thinner than the gap still shows.
  assert.ok((donutArcs([0.995, 0.005], 0.01)[1]?.length ?? 0) > 0);
});

test("axis ticks are round and reach the largest value", () => {
  assert.deepEqual(niceTicks(3_000_000), [0, 1_000_000, 2_000_000, 3_000_000]);
  assert.deepEqual(niceTicks(4_200_000), [0, 2_000_000, 4_000_000, 6_000_000]);
  assert.deepEqual(niceTicks(0), [0]);
});

test("labels read in Indian units and shares never round a sliver to nothing", () => {
  assert.equal(compactMoney(1_000_000), "₹10K");
  assert.equal(compactMoney(12_000_000), "₹1.2L");
  assert.equal(sharePercent(0.004), "<1%");
  assert.equal(sharePercent(0.426), "43%");
});

test("a running month averages over the days so far, a past month over all of it", () => {
  assert.equal(daysCounted("2026-10-01", "2026-10-31", "2026-10-15"), 15);
  assert.equal(daysCounted("2026-09-01", "2026-09-30", "2026-10-15"), 30);
});
