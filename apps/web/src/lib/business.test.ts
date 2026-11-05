import assert from "node:assert/strict";
import { test } from "node:test";
import { BUSINESS } from "./business.ts";

test("public business details are verified values or left out, never placeholders", () => {
  for (const [field, value] of Object.entries(BUSINESS)) {
    if (value === null) continue;
    assert.doesNotMatch(value, /pending|todo|tbd|\[|\]/i, `${field} looks like a placeholder`);
  }
  assert.match(BUSINESS.email, /^[a-z]+@finboy\.io$/);
});
