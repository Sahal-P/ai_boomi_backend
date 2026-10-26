import { ArrowDownLeft, ArrowLeftRight, ArrowUpRight, Ban, Undo2 } from "lucide-react";
import type { BaseTransaction, Transaction } from "@/lib/api/money";
import { formatMoney } from "@/lib/api/money";
import { sourceLabels } from "@/lib/labels";
import { cn } from "@/lib/utils";

/** Direction/kind glyph; failed attempts, transfers and refunds look different from spending. */
export function RecordGlyph({
  row,
  className,
}: {
  row: Pick<BaseTransaction, "direction" | "kind" | "status">;
  className?: string;
}) {
  const failed = row.status === "failed";
  const transfer = row.kind === "transfer";
  const refund = row.kind === "refund" || row.kind === "reversal";
  const Icon = failed ? Ban : transfer ? ArrowLeftRight : refund ? Undo2 : row.direction === "in" ? ArrowDownLeft : ArrowUpRight;
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-10 shrink-0 place-items-center rounded-full",
        failed || transfer
          ? "bg-muted text-ink-soft"
          : row.direction === "in"
            ? "bg-emerald-50 text-positive"
            : "bg-white/80 text-ink ring-1 ring-ink/[0.06]",
        className,
      )}
    >
      <Icon className="size-5" />
    </span>
  );
}

/** Signed amount for display; failed attempts never read as money that moved. */
export function RecordAmount({
  row,
  className,
}: {
  row: Pick<BaseTransaction, "direction" | "amount_minor" | "status">;
  className?: string;
}) {
  if (row.status === "failed") {
    return (
      <span className={cn("tabular-nums text-ink-soft line-through", className)}>
        <span className="sr-only">Failed payment of </span>
        {formatMoney(row.amount_minor)}
      </span>
    );
  }
  return (
    <span className={cn("tabular-nums", className)}>
      <span aria-hidden="true">{row.direction === "in" ? "+" : "−"}</span>
      <span className="sr-only">{row.direction === "in" ? "Money in: " : "Money out: "}</span>
      {formatMoney(row.amount_minor)}
    </span>
  );
}

export function SourceTags({ row }: { row: Pick<Transaction, "source_modes" | "source_count"> }) {
  const modes = row.source_modes.length ? row.source_modes : [];
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {modes.map((mode) => (
        <span key={mode} className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-semibold text-ink-soft">
          {sourceLabels[mode]}
        </span>
      ))}
      {row.source_count > 1 && (
        <span className="text-[11px] font-medium text-ink-soft">{row.source_count} emails</span>
      )}
    </span>
  );
}
