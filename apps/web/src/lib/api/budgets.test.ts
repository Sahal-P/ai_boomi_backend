import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { budgetPlanSchema, getBudgets, setBudget, setGoal } from "./budgets.ts";

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

const plan = {
  period_start: "2026-10-01",
  period_end: "2026-10-31",
  as_of: "2026-10-29",
  income_minor: 3000000,
  spent_minor: 1845000,
  saved_minor: 1155000,
  goal_minor: 500000,
  items: [{ category: "food_dining", limit_minor: 500000, spent_minor: 420000, level: "near" }],
  categories: ["total", "food_dining", "groceries"],
};

test("a budget plan is checked before the Overview shows it", () => {
  assert.equal(budgetPlanSchema.parse(plan).items[0]?.level, "near");
  const bad = (change: object) => budgetPlanSchema.safeParse({ ...plan, ...change }).success;
  assert.equal(bad({ items: [{ ...plan.items[0], category: "salary_bonus" }] }), false);
  assert.equal(bad({ items: [{ ...plan.items[0], level: "fine" }] }), false);
  assert.equal(bad({ items: [{ ...plan.items[0], limit_minor: 0 }] }), false);
  assert.equal(bad({ goal_minor: 1.5 }), false);
  // Overspending is a negative amount kept, and refunds can take spending below zero.
  assert.equal(bad({ saved_minor: -2500 }), true);
  assert.equal(bad({ items: [{ ...plan.items[0], spent_minor: -100 }] }), true);
});

test("budgets are read for a period and changed with PATCH", async () => {
  const calls: { url: string; method: string; body: unknown }[] = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
    return new Response(JSON.stringify(plan), { status: 200 });
  };
  await getBudgets({ year: 2026, month: 9 });
  await setBudget("total", 2000000);
  await setBudget("food_dining", null);
  await setGoal(null);
  assert.deepEqual(
    calls.map(({ url, method, body }) => [url.replace(/^.*\/api\/v1/, ""), method, body]),
    [
      ["/money/budgets?period=month&year=2026&month=9", "GET", null],
      ["/money/budgets", "PATCH", { category: "total", limit_minor: 2000000 }],
      ["/money/budgets", "PATCH", { category: "food_dining", limit_minor: null }],
      ["/money/goal", "PATCH", { goal_minor: null }],
    ],
  );
});
