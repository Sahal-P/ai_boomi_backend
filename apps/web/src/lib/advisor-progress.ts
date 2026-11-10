// What Ask says while the advisor works, from the step the API streams (advisor phase 2).
const labels = new Map<string, string>([
  ["thinking", "Thinking…"],
  ["money_summary", "Adding up your money…"],
  ["category_spending", "Looking at your spending…"],
  ["find_payments", "Finding your payments…"],
  ["payees_and_people", "Checking who you pay…"],
  ["dues", "Checking your dues…"],
  ["budgets_and_goal", "Checking your budgets and goal…"],
  ["compare", "Comparing the two periods…"],
  ["afford_monthly", "Seeing if it fits your month…"],
  ["plan_numbers", "Working out the numbers…"],
  ["search_past_chats", "Looking through your earlier chats…"],
  ["search_knowledge", "Reading FinBoy's money guides…"],
]);

/** The words for a step; an unknown or missing step reads as "Thinking…". */
export function progressLabel(stage: string | null | undefined): string {
  return (stage ? labels.get(stage) : undefined) ?? "Thinking…";
}
