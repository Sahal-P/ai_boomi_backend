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
      className={cn(
        "flex w-full items-start gap-3 px-4 py-4 text-left transition-colors hover:bg-lilac/30 sm:px-5",
        selected && "bg-lilac/50 hover:bg-lilac/50",
      )}
    >
      <RecordGlyph row={row} />
      <span className="min-w-0 flex-1">
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
      <span className="shrink-0 text-right">
        <RecordAmount row={row} className="block text-sm font-semibold" />
        {!compact && (
          <span className="mt-1 block max-w-36 text-[11px] leading-snug text-ink-soft">
            {effectLabel(row)}
          </span>
        )}
      </span>
    </Link>
  );
}
