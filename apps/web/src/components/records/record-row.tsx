import Link from "next/link";
import { RecordAmount, RecordGlyph, SourceTags } from "@/components/records/record-bits";
import type { Transaction } from "@/lib/api/money";
import { formatDay } from "@/lib/dates";
import { categoryLabels, effectLabel, kindLabels, reasonFor, statusLabels } from "@/lib/labels";
import { cn } from "@/lib/utils";

/**
 * One record as a real link to its exact detail (`?selected=id`), so it can be opened in a
 * new tab, shared within the household and restored with Back.
 */
export function RecordRow({
  row,
  href,
  selected = false,
  replace = false,
  showReason = true,
  compact = false,
}: {
  row: Transaction;
  href: string;
  selected?: boolean;
  replace?: boolean;
  showReason?: boolean;
  /** Queue layout: every row is unresolved, so the effect and status chips are implied. */
  compact?: boolean;
}) {
  const reason = showReason ? reasonFor(row) : null;
  return (
    <Link
      href={href}
      replace={replace}
      scroll={false}
      data-record-id={row.id}
      aria-current={selected ? "true" : undefined}
      // One effect label, placed by the grid: under the details on phones (the merchant keeps the
      // width), under the amount on wider screens.
      className={cn(
        "surface grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 rounded-lg px-3.5 py-3 text-left transition-colors hover:bg-white/70 sm:px-4",
        selected && "bg-white/90 ring-[1.5px] ring-ink hover:bg-white/90",
      )}
    >
      <RecordGlyph row={row} className="row-span-2" />
      <span className="col-start-2 row-start-1 min-w-0 sm:row-span-2">
        {reason && (
          <span className="mb-0.5 block text-xs font-semibold text-amber-900">{reason.title}</span>
        )}
        <span className="block text-sm font-semibold break-words">{row.merchant}</span>
        <span className="mt-0.5 block text-xs text-ink-soft">
          {kindLabels[row.kind]} · {categoryLabels[row.category]} · {formatDay(row.occurred_at)}
        </span>
        <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
          {row.status !== "confirmed" && !compact && (
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                row.status === "needs_review" ? "bg-amber-50 text-amber-900" : "bg-muted text-ink-soft",
              )}
            >
              {statusLabels[row.status]}
            </span>
          )}
          {row.dataset === "quarantined" && (
            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-900">
              On hold
            </span>
          )}
          <SourceTags row={row} />
        </span>
      </span>
      <RecordAmount row={row} className="col-start-3 row-start-1 block text-right text-[15px] font-semibold" />
      {!compact && (
        <span className="col-span-2 col-start-2 row-start-2 mt-1.5 block text-[11px] leading-snug text-ink-soft sm:col-span-1 sm:col-start-3 sm:mt-1 sm:max-w-36 sm:justify-self-end sm:text-right">
          {effectLabel(row)}
        </span>
      )}
    </Link>
  );
}
