import assert from "node:assert/strict";
import { test } from "node:test";
import { diaryCsv, diaryTotals, parseRupees, type DiaryEntry } from "./cash-upi-diary.ts";

const entries: DiaryEntry[] = [
  { id: 1, date: "2026-11-15", description: 'Tea, "large"', method: "Cash", category: "Food and groceries", amountMinor: 2050 },
  { id: 2, date: "2026-11-15", description: "=1+1", method: "UPI", category: "Transport", amountMinor: 12005 },
];

test("rupee amounts accept only positive values with at most two decimal places", () => {
  assert.equal(parseRupees("20"), 2000);
  assert.equal(parseRupees("120.05"), 12005);
  assert.equal(parseRupees("0.1"), 10);
  for (const value of ["", "0", "-3", "1.001", "1e3", "1,000", "1000000000", "₹20"]) {
    assert.equal(parseRupees(value), null);
  }
});

test("totals use integer paise and stay separate by payment method", () => {
  assert.deepEqual(diaryTotals(entries), { Cash: 2050, UPI: 12005, total: 14055 });
  assert.deepEqual(diaryTotals([]), { Cash: 0, UPI: 0, total: 0 });
});

test("CSV quotes text and neutralises spreadsheet formulas", () => {
  const csv = diaryCsv(entries);
  assert.match(csv, /^\uFEFF"Date","Description"/);
  assert.match(csv, /"Tea, ""large"""/);
  assert.match(csv, /"'=1\+1"/);
  assert.match(csv, /"120\.05"/);
  const first = entries[0];
  assert.ok(first);
  for (const description of ["  +SUM(A1)", "\t@x", "-1", "\r=x"]) {
    assert.ok(diaryCsv([{ ...first, description }]).includes(`"'${description}"`));
  }
});
