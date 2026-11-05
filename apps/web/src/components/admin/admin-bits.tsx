import { RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import type { Resource } from "@/hooks/use-resource";
import { formatDay, formatDayTime } from "@/lib/dates";
import { cn } from "@/lib/utils";

// Presentational pieces shared by the admin screens. Values come from the API as given.

export const count = (value: number) => value.toLocaleString("en-IN");

/** "3 Nov 2026" or an em dash when there is no date. */
export const day = (value: string | null | undefined) => (value ? formatDay(value) : "—");
export const moment = (value: string | null | undefined) => (value ? formatDayTime(value) : "—");

/** Loads a page's data again; disabled while it is already loading. */
export function RefreshButton<T>({ resource }: { resource: Resource<T> }) {
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label="Refresh"
      onClick={resource.reload}
      disabled={resource.status === "loading" || resource.status === "refreshing"}
    >
      <RefreshCw aria-hidden="true" />
    </Button>
  );
}

/** A glass card with its own heading. */
export function Panel({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-label={title} className={cn("surface min-w-0 rounded-3xl p-5 sm:p-6", className)}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold">{title}</h2>
          {description && <p className="mt-1 text-xs leading-relaxed text-ink-soft">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** One headline number (the stat-tile contract: label, value, a line of context). */
export function StatTile({ label, value, detail }: { label: string; value: string; detail?: ReactNode }) {
  return (
    <div className="surface min-w-0 rounded-3xl p-5">
      <p className="text-xs font-semibold text-ink-soft">{label}</p>
      <p className="mt-1.5 text-[1.75rem] leading-none font-semibold tracking-[-0.025em]">{value}</p>
      {detail && <p className="mt-2 text-xs leading-relaxed text-ink-soft">{detail}</p>}
    </div>
  );
}

/**
 * Used against a limit, as the budget meters show it: an ink track, green under 80%, amber to
 * the limit, red at or over it. The words carry the numbers; the bar only repeats them.
 */
export function Meter({ label, used, limit, unit }: { label: string; used: number; limit: number; unit?: string }) {
  const share = limit > 0 ? used / limit : 0;
  const fill = share >= 1 ? "bg-negative" : share >= 0.8 ? "bg-warning" : "bg-positive";
  return (
    <div>
      <p className="flex flex-wrap justify-between gap-x-3 text-sm">
        <span className="font-medium">{label}</span>
        <span className="tabular-nums">
          <strong>{count(used)}</strong>
          <span className="text-ink-soft">
            {" "}
            of {count(limit)}
            {unit ? ` ${unit}` : ""}
          </span>
        </span>
      </p>
      <span className="mt-2 block h-2 overflow-hidden rounded-full bg-ink/[0.07]" aria-hidden="true">
        <span
          className={cn("block h-full origin-left animate-grow-x rounded-full", fill)}
          style={{ width: `${Math.min(100, Math.max(used > 0 ? 2 : 0, share * 100))}%` }}
        />
      </span>
    </div>
  );
}

/** Counts by a fixed code: a small table, largest first, with a line when there are none. */
export function CountTable({
  caption,
  rows,
  empty,
}: {
  caption: string;
  rows: { key: string; label: string; value: number }[];
  empty: string;
}) {
  const shown = rows.filter((row) => row.value > 0).sort((a, b) => b.value - a.value);
  if (!shown.length) return <p className="text-sm text-ink-soft">{empty}</p>;
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">State</th>
          <th scope="col">Count</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-ink/[0.07]">
        {shown.map((row) => (
          <tr key={row.key}>
            <th scope="row" className="py-2 text-left font-medium">
              {row.label}
            </th>
            <td className="py-2 text-right font-semibold tabular-nums">{count(row.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Label and value pairs. */
export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
      {items.map(([name, value]) => (
        <div key={name} className="contents">
          <dt className="text-ink-soft">{name}</dt>
          <dd className="min-w-0 text-right font-medium break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Previous / next for an offset-paged list of 50. */
export function Pager({
  label,
  offset,
  shown,
  total,
  nextOffset,
  onPage,
}: {
  label: string;
  offset: number;
  shown: number;
  total: number;
  nextOffset: number | null;
  onPage: (offset: number) => void;
}) {
  if (offset === 0 && nextOffset === null) return null;
  return (
    <nav aria-label={label} className="mt-3 flex items-center justify-between gap-2">
      <Button variant="ghost" size="sm" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - 50))}>
        Previous
      </Button>
      <p className="text-xs text-ink-soft tabular-nums">
        {count(offset + 1)}–{count(offset + shown)} of {count(total)}
      </p>
      <Button variant="ghost" size="sm" disabled={nextOffset === null} onClick={() => nextOffset !== null && onPage(nextOffset)}>
        Next
      </Button>
    </nav>
  );
}
