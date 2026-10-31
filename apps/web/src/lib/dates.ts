// One human date style for the product. Calendar dates are shown as written; instants in IST.
const IST = "Asia/Kolkata";

const day = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const dayInIst = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: IST,
});
const dayTime = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: IST,
});
const monthYear = new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" });

const isDateOnly = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value);

function calendarDate(value: string): Date {
  const [year, month, date] = value.split("-").map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, date ?? 1);
}

/** "24 Oct 2026" — for ISO dates (as written) and timestamps (IST calendar day). */
export function formatDay(value: string): string {
  return isDateOnly(value) ? day.format(calendarDate(value)) : dayInIst.format(new Date(value));
}

/** "24 Oct 2026, 9:00 am IST" — for instants where the time matters. */
export function formatDayTime(value: string): string {
  return isDateOnly(value) ? formatDay(value) : `${dayTime.format(new Date(value))} IST`;
}

export function formatRange(start: string | null, end: string | null): string | null {
  if (!start || !end) return null;
  return `${formatDay(start)} – ${formatDay(end)}`;
}

/** "October 2026" for a whole calendar month, else "1 Oct 2026 – 24 Oct 2026" (or one day). */
export function formatPeriod(start: string, end: string): string {
  const first = calendarDate(start);
  const monthEnd = new Date(first.getFullYear(), first.getMonth() + 1, 0);
  if (first.getDate() === 1 && calendarDate(end).getTime() === monthEnd.getTime()) return monthYear.format(first);
  return start === end ? formatDay(start) : `${formatDay(start)} – ${formatDay(end)}`;
}

export function monthLabel(year: number, month: number): string {
  return monthYear.format(new Date(year, month - 1, 1));
}

export type Month = { year: number; month: number };

/** `count` calendar months ending with (and including) year-month, newest first. */
export function monthsBack(year: number, month: number, count: number): Month[] {
  return Array.from({ length: count }, (_, index) => {
    const offset = month - 1 - index;
    return { year: year + Math.floor(offset / 12), month: (((offset % 12) + 12) % 12) + 1 };
  });
}

/** The current IST month and the ones before it, newest first. */
export function recentMonths(count: number, now: Date = new Date()): Month[] {
  const [year = 2026, month = 1] = istDate(now).split("-").map(Number);
  return monthsBack(year, month, count);
}

/** Calendar date in IST for an instant, as YYYY-MM-DD (date inputs, comparisons). */
export function istDate(value: string | Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: IST,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(typeof value === "string" ? new Date(value) : value);
  return parts;
}

/** Moves an instant to another IST calendar date, keeping its IST time of day (RFC 3339). */
export function withIstDate(original: string, date: string): string {
  const time = new Intl.DateTimeFormat("en-GB", {
    timeZone: IST,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(new Date(original));
  return `${date}T${time}+05:30`;
}
