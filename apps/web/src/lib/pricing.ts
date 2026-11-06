/**
 * FinBoy's published plans (docs/subscription-round/contract.md), shared by the landing page and
 * /pricing so the two never disagree. The API's plan carries what is actually charged.
 */
export const FREE_FEATURES = [
  "Typed entries on WhatsApp and the web",
  "Home, Transactions and Reports",
  "Budgets and a savings goal",
  "“Today”, “this week” and “this month” check-ups on WhatsApp",
  // Advisor round (docs/advisor-round/contract.md): asking is for every household.
  "Ask FinBoy about your money, with answers from your own records",
  "FinBoy remembers your goals and plans, and you can see or delete what it keeps",
] as const;

export const PREMIUM_FEATURES = [
  "Everything in Free",
  "Voice notes and spoken replies, in English, Hindi and Malayalam",
  "Photos of bills and UPI screenshots, read for you",
  "Months of history from a Google Pay statement",
] as const;

/** Every new household's Premium days before the Free plan (or a payment) takes over. */
export const TRIAL_DAYS = 30;
