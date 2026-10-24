import assert from "node:assert/strict";
import { test } from "node:test";
import { safeReturnPath } from "./auth.ts";

test("sign-in returns only to same-origin app paths", () => {
  assert.equal(safeReturnPath("/import/30000000-0000-4000-8000-000000000001"), "/import/30000000-0000-4000-8000-000000000001");
  assert.equal(safeReturnPath("/transactions?selected=abc&q=food"), "/transactions?selected=abc&q=food");
  assert.equal(safeReturnPath("/sources?intent=gmail"), "/sources?intent=gmail");
  for (const unsafe of [
    null,
    "",
    "https://evil.example/dashboard",
    "//evil.example/dashboard",
    "/\\evil.example",
    "javascript:alert(1)",
    "/login",
    "/api/v1/money/summary",
    "/dashboard/../api/v1/auth/logout",
    `/review?${"x".repeat(600)}`,
  ]) {
    assert.equal(safeReturnPath(unsafe), "/dashboard", String(unsafe));
  }
});
