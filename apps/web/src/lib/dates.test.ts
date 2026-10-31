import assert from "node:assert/strict";
import { test } from "node:test";
import { formatPeriod, monthsBack, recentMonths } from "./dates.ts";

test("month lists run newest first and cross year boundaries", () => {
  assert.deepEqual(monthsBack(2026, 2, 3), [
    { year: 2026, month: 2 },
    { year: 2026, month: 1 },
    { year: 2025, month: 12 },
  ]);
  // 31 Oct 2026, 20:00 UTC is already 1 Nov in IST.
  assert.deepEqual(recentMonths(2, new Date("2026-10-31T20:00:00Z")), [
    { year: 2026, month: 11 },
    { year: 2026, month: 10 },
  ]);
});

test("answer periods read as a month or a day range, never an ISO range", () => {
  assert.equal(formatPeriod("2026-10-01", "2026-10-31"), "October 2026");
  assert.equal(formatPeriod("2026-02-01", "2026-02-28"), "February 2026");
  assert.equal(formatPeriod("2026-10-01", "2026-10-24"), "1 Oct 2026 – 24 Oct 2026");
  assert.equal(formatPeriod("2026-10-23", "2026-10-23"), "23 Oct 2026");
});
