import assert from "node:assert/strict";
import { test } from "node:test";
import { formatPeriod } from "./dates.ts";

test("answer periods read as a month or a day range, never an ISO range", () => {
  assert.equal(formatPeriod("2026-10-01", "2026-10-31"), "October 2026");
  assert.equal(formatPeriod("2026-02-01", "2026-02-28"), "February 2026");
  assert.equal(formatPeriod("2026-10-01", "2026-10-24"), "1 Oct 2026 – 24 Oct 2026");
  assert.equal(formatPeriod("2026-10-23", "2026-10-23"), "23 Oct 2026");
});
