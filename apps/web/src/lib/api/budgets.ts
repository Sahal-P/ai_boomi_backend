import { z } from "zod";
import { jsonBody, query, requestJson } from "./http.ts";
import { categorySchema, periodQuery, type Period } from "./money.ts";

/** A monthly budget is for one spending category, or "total" for all spending. */
export const budgetCategorySchema = z.union([z.literal("total"), categorySchema]);
export type BudgetCategory = z.infer<typeof budgetCategorySchema>;

const integer = z.number().int().safe();
const minor = integer.nonnegative();

export const budgetItemSchema = z.object({
  category: budgetCategorySchema,
  limit_minor: integer.positive(),
  spent_minor: integer, // net of refunds, so all spending can dip below zero
  level: z.enum(["ok", "near", "over"]),
});
export type BudgetItem = z.infer<typeof budgetItemSchema>;

export const budgetPlanSchema = z.object({
  period_start: z.iso.date(),
  period_end: z.iso.date(),
  as_of: z.iso.date(),
  income_minor: minor,
  spent_minor: integer,
  // Income minus spending, with money put into savings counted as kept; negative when overspent.
  saved_minor: integer,
  goal_minor: integer.positive().nullable(),
  items: z.array(budgetItemSchema).max(30),
  categories: z.array(budgetCategorySchema).max(30),
});
export type BudgetPlan = z.infer<typeof budgetPlanSchema>;

export const getBudgets = (period: Period, signal?: AbortSignal) =>
  requestJson(`/api/v1/money/budgets${query(periodQuery(period))}`, budgetPlanSchema, { signal });

/** Sets one monthly budget, or removes it with null. */
export const setBudget = (category: BudgetCategory, limitMinor: number | null) =>
  requestJson("/api/v1/money/budgets", budgetPlanSchema, {
    method: "PATCH",
    ...jsonBody({ category, limit_minor: limitMinor }),
  });

/** Sets the monthly savings goal, or clears it with null. */
export const setGoal = (goalMinor: number | null) =>
  requestJson("/api/v1/money/goal", budgetPlanSchema, {
    method: "PATCH",
    ...jsonBody({ goal_minor: goalMinor }),
  });
