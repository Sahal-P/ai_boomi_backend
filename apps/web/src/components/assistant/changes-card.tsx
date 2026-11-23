"use client";

import { Check, Lock, PencilLine, RotateCcw } from "lucide-react";
import { useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import {
  applyChanges,
  dismissChanges,
  undoChanges,
  type ChangeGroup,
  type ChangeSet,
} from "@/lib/api/assistant";
import { categories, formatMoney, type Category } from "@/lib/api/money";
import { categoryLabels } from "@/lib/labels";
import { describeProblem, hasCode, type Problem } from "@/lib/messages";
import { emitRecordsChanged } from "@/lib/record-events";

type Action = "apply" | "undo" | "dismiss";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;
const known = new Set<string>(categories);

function label(category: string | null): string {
  if (category === null || category === "total") return "All spending";
  return known.has(category) ? categoryLabels[category as Category] : categoryLabels.other;
}

function monthly(minor: number | null): string {
  return minor === null ? "removed" : `${formatMoney(minor)} a month`;
}

/** One line, worked out by FinBoy: where payments move, how many and how much. */
export function changeLine(group: ChangeGroup): { title: string; detail: string } {
  if (group.kind === "budget" || group.kind === "savings_goal") {
    return {
      title: group.kind === "budget" ? `${label(group.category)} budget` : "Savings goal",
      detail:
        group.before_minor === null
          ? monthly(group.after_minor)
          : `${monthly(group.before_minor)} → ${monthly(group.after_minor)}`,
    };
  }
  const names = group.names.join(", ") + (group.more_names ? ` +${group.more_names} more` : "");
  const payments = plural(group.payments, "payment", "payments");
  if (group.kind === "rename") return { title: `New name: ${group.new_name ?? ""}`, detail: `${names} · ${payments}` };
  return {
    title: group.kind === "own_transfer" ? "Own accounts · not spending" : label(group.category),
    detail: `${names} · ${payments} · ${formatMoney(group.amount_minor)}`,
  };
}

const headings: Record<ChangeSet["state"], string> = {
  proposed: "FinBoy can make these changes",
  applied: "Changes made",
  undone: "Put back as it was",
  declined: "Not applied",
  expired: "These changes expired",
};

function summary(changeSet: ChangeSet): string {
  const { state, count, skipped } = changeSet;
  if (state === "proposed") return "Nothing changes until you tap Apply. One Undo puts it all back.";
  if (state === "applied") {
    const made = `${plural(count, "change", "changes")} made.`;
    const kept = changeSet.remembered ? " FinBoy will remember these payees for their next payments." : "";
    return skipped
      ? `${made} ${plural(skipped, "change", "changes")} no longer applied, so FinBoy left them.${kept}`
      : `${made}${kept}`;
  }
  if (state === "undone") {
    return skipped
      ? `${plural(skipped, "change", "changes")} made since stay as they are.`
      : "Everything is back as it was.";
  }
  if (state === "declined") return "Nothing changed.";
  return "Nothing changed. Ask FinBoy again to see them for your records as they are now.";
}

/**
 * Changes an advisor answer proposed (docs/advisor-edits-round/contract.md): what would change,
 * Apply and Not now, then the result with one Undo. Every line comes from FinBoy's own figures.
 */
export function ChangesCard({ changeSet, onChange }: { changeSet: ChangeSet; onChange: (next: ChangeSet) => void }) {
  const [busy, setBusy] = useState<Action | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState("");
  const { state } = changeSet;
  const done = state === "applied";

  async function act(action: Action) {
    if (busy) return;
    setBusy(action);
    setProblem(null);
    try {
      const run = action === "apply" ? applyChanges : action === "undo" ? undoChanges : dismissChanges;
      const next = await run(changeSet.id);
      onChange(next);
      if (action !== "dismiss") emitRecordsChanged();
      setNotice(`${headings[next.state]}. ${summary(next)}`);
    } catch (error) {
      if (hasCode(error, "changes_expired")) {
        onChange({ ...changeSet, state: "expired" });
        setNotice(`${headings.expired}. ${summary({ ...changeSet, state: "expired" })}`);
        return;
      }
      setProblem(
        describeProblem(
          error,
          action === "apply" ? "The changes weren't made" : action === "undo" ? "Nothing was put back" : "That didn't work",
        ),
      );
    } finally {
      setBusy(null);
    }
  }

  const Icon = done ? Check : state === "undone" ? RotateCcw : PencilLine;
  return (
    <section
      aria-label={headings[state]}
      className="space-y-3 rounded-2xl bg-white/60 p-4 ring-1 ring-ink/5"
      lang="en"
      data-state={state}
    >
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-ink/[0.07]" aria-hidden="true">
          <Icon className="size-4 text-ink" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-semibold text-ink">
            {headings[state]}
            {state === "proposed" && <span className="font-normal text-ink-soft"> · {plural(changeSet.count, "change", "changes")}</span>}
          </h3>
          <p className="text-sm text-ink-soft">{summary(changeSet)}</p>
        </div>
      </div>
      <ul className={state === "proposed" || done ? "space-y-2" : "space-y-2 opacity-70"}>
        {changeSet.groups.map((group, index) => {
          const line = changeLine(group);
          return (
            <li
              key={`${group.kind}-${group.category ?? ""}-${group.new_name ?? ""}-${index}`}
              className="flex flex-col gap-0.5 rounded-xl bg-white/70 px-3 py-2 text-sm ring-1 ring-ink/5"
            >
              <span className="font-semibold break-words text-ink">{line.title}</span>
              <span className="break-words text-ink-soft tabular-nums">{line.detail}</span>
            </li>
          );
        })}
      </ul>
      {changeSet.kept > 0 && (
        <p className="flex items-start gap-2 text-sm text-ink-soft">
          <Lock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {plural(changeSet.kept, "payment", "payments")} you set yourself stay as they are.
        </p>
      )}
      {(state === "proposed" || done) && (
        <div className="flex flex-col gap-2 sm:flex-row">
          {state === "proposed" ? (
            <>
              <Button className="min-h-11" disabled={busy !== null} onClick={() => void act("apply")}>
                <Check aria-hidden="true" />
                {busy === "apply" ? "Applying…" : `Apply ${plural(changeSet.count, "change", "changes")}`}
              </Button>
              <Button variant="outline" className="min-h-11" disabled={busy !== null} onClick={() => void act("dismiss")}>
                Not now
              </Button>
            </>
          ) : (
            <Button variant="outline" className="min-h-11" disabled={busy !== null} onClick={() => void act("undo")}>
              <RotateCcw aria-hidden="true" />
              {busy === "undo" ? "Putting back…" : "Undo"}
            </Button>
          )}
        </div>
      )}
      <p role="status" aria-live="polite" className="sr-only">
        {notice}
      </p>
      {problem && <ProblemNotice problem={problem} />}
    </section>
  );
}
