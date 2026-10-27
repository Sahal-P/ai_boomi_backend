import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { entryPreviewSchema, saveEntry } from "./entries.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("a preview is a reading, never a saved record", () => {
  const preview = entryPreviewSchema.parse({
    kind: "spent",
    amount_minor: 50000,
    counterparty: "Milkman",
    category: "groceries",
    day: "2026-10-27",
    due_date: null,
    label: null,
  });
  assert.equal(preview.amount_minor, 50000);
  assert.equal(entryPreviewSchema.safeParse({ ...preview, amount_minor: -1 }).success, false);
  assert.equal(entryPreviewSchema.safeParse({ ...preview, category: "lottery" }).success, false);
});

test("save sends only the fields the kind needs", async () => {
  const sent: unknown[] = [];
  globalThis.fetch = async (_url, init) => {
    sent.push(JSON.parse(String(init?.body)));
    return new Response(
      JSON.stringify({
        kind: "record",
        transaction_id: "30000000-0000-4000-8000-000000000001",
        decision_id: "30000000-0000-4000-8000-000000000002",
        obligation_id: null,
        data_version: "3:2026-10-27",
      }),
      { status: 200 },
    );
  };
  const base = { amount_minor: 50000, counterparty: "Milkman", label: "Milkman", category: "groceries" as const };
  await saveEntry({ ...base, kind: "spent", day: "2026-10-27", due_date: null });
  await saveEntry({ ...base, kind: "due", day: null, due_date: "2026-11-10", label: "School fees" });
  assert.deepEqual(sent, [
    { kind: "spent", amount_minor: 50000, counterparty: "Milkman", category: "groceries", day: "2026-10-27" },
    { kind: "due", amount_minor: 50000, label: "School fees", category: "groceries", due_date: "2026-11-10" },
  ]);
});
