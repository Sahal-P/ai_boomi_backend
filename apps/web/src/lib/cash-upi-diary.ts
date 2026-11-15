export const DIARY_CATEGORIES = ["Food and groceries", "Transport", "Bills", "Shopping", "Other"] as const;
export type DiaryCategory = (typeof DIARY_CATEGORIES)[number];
export type PaymentMethod = "Cash" | "UPI";
export type DiaryEntry = {
  id: number;
  date: string;
  description: string;
  method: PaymentMethod;
  category: DiaryCategory;
  amountMinor: number;
};

/** Parse rupees without floating-point arithmetic. */
export function parseRupees(value: string): number | null {
  const match = /^(\d{1,9})(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!match) return null;
  const amount = Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
  return amount > 0 ? amount : null;
}

export function diaryTotals(entries: readonly DiaryEntry[]) {
  return entries.reduce(
    (totals, entry) => {
      totals[entry.method] += entry.amountMinor;
      totals.total += entry.amountMinor;
      return totals;
    },
    { Cash: 0, UPI: 0, total: 0 },
  );
}

function csvCell(value: string): string {
  // A quoted CSV cell can still be interpreted as a formula by spreadsheet apps.
  const safe = /^[=+\-@]/u.test(value.trimStart()) || (value.length > 0 && value.charCodeAt(0) < 32)
    ? `'${value}`
    : value;
  return `"${safe.replaceAll('"', '""')}"`;
}

export function diaryCsv(entries: readonly DiaryEntry[]): string {
  const lines = [
    ["Date", "Description", "Payment method", "Category", "Amount (INR)"],
    ...entries.map((entry) => [
      entry.date,
      entry.description,
      entry.method,
      entry.category,
      `${Math.floor(entry.amountMinor / 100)}.${String(entry.amountMinor % 100).padStart(2, "0")}`,
    ]),
  ];
  return "\uFEFF" + lines.map((line) => line.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
