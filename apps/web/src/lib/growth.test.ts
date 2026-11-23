import assert from "node:assert/strict";
import { test } from "node:test";
import {
  axisLabel,
  cohortTitle,
  comparison,
  funnelSteps,
  percentOf,
  pointTitle,
  rampStep,
  showsLabel,
  signed,
} from "./growth.ts";

test("points are named for their day, week or month, and the running one says so far", () => {
  assert.equal(axisLabel("2026-11-24", "day"), "24 Nov");
  assert.equal(axisLabel("2026-11-23", "week"), "23 Nov");
  assert.equal(axisLabel("2026-11-01", "month"), "Nov");
  assert.equal(pointTitle({ start: "2026-11-24", partial: true }, "day"), "Tue, 24 Nov (so far)");
  assert.equal(pointTitle({ start: "2026-11-16", partial: false }, "week"), "Week of 16 Nov");
  assert.equal(pointTitle({ start: "2026-10-01", partial: false }, "month"), "October 2026");
  assert.equal(cohortTitle("2026-11-16", "week"), "Week of 16 Nov");
  assert.equal(cohortTitle("2026-11-01", "month"), "November 2026");
});

test("thirty days show about six axis labels ending on today; twelve show all", () => {
  const shown = Array.from({ length: 30 }, (_, index) => index).filter((index) => showsLabel(index, 30));
  assert.deepEqual(shown, [4, 9, 14, 19, 24, 29]);
  assert.ok(Array.from({ length: 12 }, (_, index) => showsLabel(index, 12)).every(Boolean));
});

test("comparisons, shares and changes read as words", () => {
  assert.deepEqual(comparison(15, 6, "30d"), { direction: "up", text: "9 more than the 30 days before" });
  assert.deepEqual(comparison(2, 5, "12w"), { direction: "down", text: "3 fewer than the 12 weeks before" });
  assert.deepEqual(comparison(4, 4, "12m"), { direction: "same", text: "Same as the 12 months before" });
  assert.equal(percentOf(6, 11), "55%");
  assert.equal(percentOf(1, 400), "<1%");
  assert.equal(percentOf(3, 0), "—");
  assert.equal(signed(9), "+9");
  assert.equal(signed(-1), "−1");
  assert.equal(signed(0), "0");
});

test("retention shares take seven ramp steps, none for nobody", () => {
  assert.deepEqual([0, 0.01, 1 / 7, 0.15, 0.5, 4 / 7, 0.58, 1].map(rampStep), [0, 1, 1, 2, 4, 4, 5, 7]);
});

test("the funnel gives each step's share of the step before and of page opens", () => {
  const steps = funnelSteps({
    opened: 363,
    tapped: 48,
    signed_up: 15,
    agreed: 11,
    first_record: 6,
    direct_signed_up: 0,
    direct_agreed: 0,
    direct_first_record: 0,
  });
  assert.deepEqual(
    steps.map((step) => [step.key, step.count, step.ofPrevious, step.ofOpened]),
    [
      ["opened", 363, null, null],
      ["tapped", 48, "13%", "13%"],
      ["signed_up", 15, "31%", "4%"],
      ["agreed", 11, "73%", "3%"],
      ["first_record", 6, "55%", "2%"],
    ],
  );
  const none = { opened: 0, tapped: 0, signed_up: 0, agreed: 0, first_record: 0 };
  const empty = funnelSteps({ ...none, direct_signed_up: 0, direct_agreed: 0, direct_first_record: 0 });
  assert.ok(empty.slice(1).every((step) => step.ofPrevious === "—" && step.ofOpened === "—"));
});
