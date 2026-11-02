import type { Plan } from "./api/billing.ts";

// Pure plan wording and dates for FinBoy Premium (docs/subscription-round/contract.md).

export type Feature = "voice" | "ask" | "photos" | "statement";

const istDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const shortDay = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });

function dayNumber(value: Date): number {
  const [year, month, day] = istDate.format(value).split("-").map(Number);
  return Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1) / 86_400_000;
}

/** Calendar days in India from today until the day `until` falls on: 0 on that day itself. */
export function daysLeft(until: string, now = new Date()): number {
  return dayNumber(new Date(until)) - dayNumber(now);
}

/** "2 Dec" in India. */
export function shortDate(value: string): string {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00+05:30`) : new Date(value);
  return shortDay.format(date);
}

export function rupees(minor: number): string {
  return `₹${(minor / 100).toLocaleString("en-IN", { maximumFractionDigits: minor % 100 ? 2 : 0 })}`;
}

/** When Premium runs out if nothing more is paid: the later of the trial and paid time. */
export function premiumUntil(plan: Plan): string | null {
  const ends = [plan.trial_ends_at, plan.paid_through].filter((value): value is string => value !== null);
  if (!ends.length) return null;
  return ends.reduce((latest, value) => (new Date(value) > new Date(latest) ? value : latest));
}

function inDays(days: number): string {
  if (days <= 0) return "ends today";
  return days === 1 ? "1 day left" : `${days} days left`;
}

/** The account menu's one-line status. */
export function statusLine(plan: Plan, now = new Date()): string {
  if (plan.state === "included") return "Premium included";
  if (plan.state === "free") return "Free plan";
  if (plan.state === "grace") return "Payment didn't go through";
  if (plan.renewal === "autopay") return "Premium · AutoPay on";
  const until = premiumUntil(plan);
  if (plan.state === "trial" && !plan.paid_through && plan.trial_ends_at) {
    return `Trial · ${inDays(daysLeft(plan.trial_ends_at, now))}`;
  }
  return until ? `Premium until ${shortDate(until)}` : "Premium";
}

/** What Home should say about the plan, if anything; quiet until the last week. */
export type Notice = { tone: "calm" | "attention"; text: string; action: string } | null;

export function homeNotice(plan: Plan | null, now = new Date()): Notice {
  if (!plan || plan.state === "included") return null;
  if (plan.state === "grace") {
    return { tone: "attention", text: "Payment didn't go through", action: "Fix" };
  }
  if (plan.state === "free") {
    return { tone: "calm", text: "You're on the free plan", action: "Get Premium" };
  }
  if (plan.renewal === "autopay") return null;
  const until = premiumUntil(plan);
  if (!until) return null;
  const days = daysLeft(until, now);
  if (days > 7) return null;
  const label = plan.state === "trial" && !plan.paid_through ? "Premium trial" : "Premium";
  return { tone: "calm", text: `${label} · ${inDays(days)}`, action: "Keep Premium" };
}

export const FEATURE_LINES: Record<Feature, string> = {
  voice: "Voice notes are part of Premium.",
  ask: "Asking FinBoy is part of Premium.",
  photos: "Reading photos and screenshots is part of Premium.",
  statement: "Importing statements is part of Premium.",
};

/** The sheet's line about when the money paid now starts to count. */
export function startsLine(plan: Plan, now = new Date()): string | null {
  const until = premiumUntil(plan);
  if (!until || new Date(until) <= now) return null;
  if (plan.state === "trial" && !plan.paid_through) {
    return `Your free trial continues until ${shortDate(until)}; your first paid month starts then.`;
  }
  return `Your next month starts on ${shortDate(until)}, when this one ends.`;
}
