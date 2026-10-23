import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { authorizeUrl } from "./mail.ts";
import { ApiError } from "./http.ts";

const previous = process.env.NEXT_PUBLIC_API_URL;
function setApiUrl(value: string | undefined) {
  if (value === undefined) delete process.env.NEXT_PUBLIC_API_URL;
  else process.env.NEXT_PUBLIC_API_URL = value;
}
afterEach(() => setApiUrl(previous));

test("Gmail authorization stays on the household origin with the production proxy", () => {
  setApiUrl("/");
  assert.equal(authorizeUrl(), "/api/v1/connections/gmail/authorize");
});

test("Gmail authorization uses the configured local backend or its default", () => {
  for (const [origin, expected] of [
    [undefined, "http://127.0.0.1:8000"],
    ["http://127.0.0.1:8002", "http://127.0.0.1:8002"],
    ["http://127.0.0.1:8002/", "http://127.0.0.1:8002"],
  ]) {
    setApiUrl(origin);
    assert.equal(authorizeUrl(), `${expected}/api/v1/connections/gmail/authorize`);
  }
});

test("Gmail authorization rejects invalid backend URLs without exposing their contents", () => {
  for (const origin of [
    "invalid", "//untrusted.example", "ftp://example.test",
    "https://user:private@example.test", "https://example.test?private=value",
    "https://example.test#private",
  ]) {
    setApiUrl(origin);
    assert.throws(authorizeUrl, (error: unknown) =>
      error instanceof ApiError && error.message === "The backend URL is not configured correctly.");
  }
});
