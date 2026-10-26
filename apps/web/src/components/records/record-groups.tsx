import type { ReactNode } from "react";
import type { Transaction } from "@/lib/api/money";
import { istDate, monthLabel } from "@/lib/dates";

/** Records under month headings (IST), as in the glass reference, keeping the list's order. */
export function RecordGroups({ rows, renderRow }: { rows: Transaction[]; renderRow: (row: Transaction) => ReactNode }) {
  const groups: { key: string; label: string; rows: Transaction[] }[] = [];
  for (const row of rows) {
    const [year = 0, month = 0] = istDate(row.occurred_at).split("-").map(Number);
    const key = `${year}-${month}`;
    const last = groups.at(-1);
    if (last?.key === key) last.rows.push(row);
    else groups.push({ key, label: monthLabel(year, month), rows: [row] });
  }
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <div key={group.key}>
          <h3 className="px-1 pb-2.5 text-lg font-medium tracking-[-0.02em]">{group.label}</h3>
          <ul className="space-y-2">{group.rows.map(renderRow)}</ul>
        </div>
      ))}
    </div>
  );
}
