import { Button } from "@/components/ui/button";
import { formatMoney } from "@/lib/api/money";
import type { TransactionDetail } from "@/lib/api/transactions";
import { formatDay, formatDayTime } from "@/lib/dates";
import { categoryLabels, kindLabels, statusLabels } from "@/lib/labels";

const decisionLabels: Record<string, string> = {
  confirm: "Confirmed",
  reject: "Rejected",
  reopen: "Reopened for review",
  correct: "Corrected",
  merge: "Merged into another record",
  "keep-separate": "Kept as a separate record",
};

const fieldLabels: Record<string, string> = {
  merchant: "Merchant",
  amount_minor: "Amount",
  category: "Category",
  occurred_at: "Date",
  direction: "Direction",
  kind: "Type",
  status: "Status",
  review_reason: "Review reason",
  merged_into_id: "Merged into",
  user_locked_fields: "Fields you control",
};

function value(field: string, raw: unknown): string {
  if (raw === null || raw === undefined) return "Not set";
  if (field === "amount_minor" && typeof raw === "number") return formatMoney(raw);
  if (field === "occurred_at" && typeof raw === "string") return formatDay(raw);
  if (field === "category" && typeof raw === "string") return categoryLabels[raw as keyof typeof categoryLabels] ?? "Other";
  if (field === "kind" && typeof raw === "string") return kindLabels[raw as keyof typeof kindLabels] ?? "Other";
  if (field === "status" && typeof raw === "string") return statusLabels[raw as keyof typeof statusLabels] ?? "Changed";
  if (field === "direction") return raw === "in" ? "Money in" : "Money out";
  if (field === "merchant" && typeof raw === "string") return raw;
  if (Array.isArray(raw)) return `${raw.length} ${raw.length === 1 ? "field" : "fields"}`;
  return "Updated";
}

/** Decisions (with backend-supported undo) and field-level revision history. */
export function RecordHistory({
  detail,
  busy,
  onUndo,
}: {
  detail: TransactionDetail;
  busy: boolean;
  onUndo: (decisionId: string) => void;
}) {
  return (
    <section aria-label="History" className="space-y-4">
      <div>
        <h3 className="font-semibold">Decisions</h3>
        {!detail.decisions.length ? (
          <p className="mt-1 text-xs text-ink-soft">No decisions yet.</p>
        ) : (
          <ol className="mt-2 space-y-2">
            {detail.decisions.map((decision) => (
              <li key={decision.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>
                  <span className="font-medium">{decisionLabels[decision.action] ?? "Decision"}</span>
                  <span className="text-xs text-ink-soft">
                    {" "}· {formatDayTime(decision.created_at)}
                    {decision.undone_at && ` · undone ${formatDayTime(decision.undone_at)}`}
                  </span>
                </span>
                {decision.can_undo && !decision.undone_at && (
                  <Button size="sm" variant="outline" disabled={busy} onClick={() => onUndo(decision.id)}>
                    Undo
                  </Button>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
      <div>
        <h3 className="font-semibold">Changes</h3>
        {!detail.revisions.length ? (
          <p className="mt-1 text-xs text-ink-soft">No corrections yet.</p>
        ) : (
          <ol className="mt-2 space-y-2">
            {detail.revisions.map((revision) => (
              <li key={revision.id} className="text-xs leading-relaxed break-words">
                <span className="font-semibold">{fieldLabels[revision.field] ?? "Detail"}</span>{" "}
                <span className="text-ink-soft">
                  · {revision.changed_by === "user" ? "you" : "FinBoy"} · {formatDayTime(revision.changed_at)}
                </span>
                <p>
                  {value(revision.field, revision.old_value)} → {value(revision.field, revision.new_value)}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
