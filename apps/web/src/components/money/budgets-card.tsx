"use client";

import { ChevronRight, Check, Pencil, Plus, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useId, useState, type FormEvent } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useResource } from "@/hooks/use-resource";
import {
  getBudgets,
  setBudget,
  setGoal,
  type BudgetCategory,
  type BudgetItem,
  type BudgetPlan,
} from "@/lib/api/budgets";
import { formatMoney, inputPaise, type Period } from "@/lib/api/money";
import { monthLabel } from "@/lib/dates";
import { categoryLabels } from "@/lib/labels";
import { describeProblem, type Problem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const budgetLabel = (category: BudgetCategory) =>
  category === "total" ? "All spending" : categoryLabels[category];

// The bar's colour and the line under it: green under 80%, amber from 80%, red once over.
const LEVEL = {
  ok: { bar: "bg-positive", note: "text-ink-soft" },
  near: { bar: "bg-warning", note: "font-semibold text-ink" },
  over: { bar: "bg-negative", note: "font-semibold text-negative" },
} as const;

type Editing = { kind: "budget"; category: BudgetCategory | null } | { kind: "goal" } | null;

/** A meter: same-ramp track; the fill grows in once (CSS, so reduced motion holds it still). */
function Bar({ share, className }: { share: number; className: string }) {
  return (
    <span className="mt-2 block h-2 overflow-hidden rounded-full bg-ink/[0.07]" aria-hidden="true">
      <span
        className={cn("block h-full origin-left animate-grow-x rounded-full", className)}
        style={{ width: `${Math.min(100, Math.max(2, share * 100))}%` }}
      />
    </span>
  );
}

function BudgetRow({ item, onEdit }: { item: BudgetItem; onEdit?: (() => void) | undefined }) {
  const left = item.limit_minor - item.spent_minor;
  const level = LEVEL[item.level];
  return (
    <li className="flex items-start gap-2 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap justify-between gap-x-3 text-sm">
          <span className="font-medium">{budgetLabel(item.category)}</span>
          <span className="tabular-nums">
            <strong>{formatMoney(Math.max(0, item.spent_minor))}</strong>
            <span className="text-ink-soft"> of {formatMoney(item.limit_minor)}</span>
          </span>
        </p>
        <Bar share={Math.max(0, item.spent_minor) / item.limit_minor} className={level.bar} />
        <p className={cn("mt-1 text-xs", level.note)}>
          {left < 0 ? `${formatMoney(-left)} over` : `${formatMoney(left)} left`}
        </p>
      </div>
      {onEdit && (
        <Button
          variant="ghost"
          size="icon-sm"
          className="mt-0.5"
          aria-label={`Change the ${budgetLabel(item.category)} budget`}
          onClick={onEdit}
        >
          <Pencil aria-hidden="true" />
        </Button>
      )}
    </li>
  );
}

function Goal({ plan, onEdit }: { plan: BudgetPlan; onEdit?: (() => void) | undefined }) {
  const goal = plan.goal_minor;
  if (goal === null) {
    if (!onEdit) return null;
    return (
      <Button variant="outline" size="sm" onClick={onEdit}>
        <Plus aria-hidden="true" /> Set a monthly savings goal
      </Button>
    );
  }
  const kept = plan.saved_minor;
  const note = !plan.income_minor
    ? "Add your income (like your salary) to see how much you keep."
    : kept >= goal
      ? "Goal reached this month."
      : kept < 0
        ? `${formatMoney(-kept)} more went out than came in.`
        : `${formatMoney(goal - kept)} to go.`;
  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap justify-between gap-x-3 text-sm">
          <span className="font-medium">Savings goal</span>
          <span className="tabular-nums">
            <strong>{formatMoney(Math.max(0, kept))}</strong>
            <span className="text-ink-soft"> kept of {formatMoney(goal)}</span>
          </span>
        </p>
        <Bar share={Math.max(0, kept) / goal} className="bg-sunflower" />
        <p className={cn("mt-1 text-xs", kept >= goal && plan.income_minor ? "font-semibold text-positive" : "text-ink-soft")}>
          {note}
        </p>
      </div>
      {onEdit && (
        <Button variant="ghost" size="icon-sm" className="mt-0.5" aria-label="Change the savings goal" onClick={onEdit}>
          <Pencil aria-hidden="true" />
        </Button>
      )}
    </div>
  );
}

function EditForm({
  plan,
  editing,
  onSaved,
  onCancel,
}: {
  plan: BudgetPlan;
  editing: NonNullable<Editing>;
  onSaved: (plan: BudgetPlan) => void;
  onCancel: () => void;
}) {
  const ids = useId();
  const existing = editing.kind === "budget" ? plan.items.find((item) => item.category === editing.category) : null;
  const unused = plan.categories.filter((category) => !plan.items.some((item) => item.category === category));
  const [category, setCategory] = useState<BudgetCategory>(
    editing.kind === "budget" ? (editing.category ?? unused[0] ?? "total") : "total",
  );
  const start = editing.kind === "goal" ? plan.goal_minor : existing?.limit_minor;
  const [amount, setAmount] = useState(start ? String(start / 100) : "");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const paise = inputPaise(amount);
  const tooBig = paise !== null && paise > 1_000_000_000;
  const removable = editing.kind === "goal" ? plan.goal_minor !== null : existing !== undefined && existing !== null;

  async function save(value: number | null) {
    setBusy(true);
    setProblem(null);
    try {
      onSaved(editing.kind === "goal" ? await setGoal(value) : await setBudget(category, value));
    } catch (error) {
      setProblem(describeProblem(error, editing.kind === "goal" ? "The goal couldn't be saved" : "The budget couldn't be saved"));
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (paise !== null && !tooBig) void save(paise);
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-2xl bg-white/55 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {editing.kind === "budget" && (
          <div className="space-y-1.5">
            <label htmlFor={`${ids}-category`} className="text-sm font-semibold">
              Budget for
            </label>
            <select
              id={`${ids}-category`}
              value={category}
              disabled={existing !== undefined && existing !== null}
              onChange={(event) => setCategory(event.target.value as BudgetCategory)}
              className="field field-select h-11 w-full rounded-lg pl-3 text-sm"
            >
              {(existing ? [existing.category] : unused).map((option) => (
                <option key={option} value={option}>
                  {budgetLabel(option)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="space-y-1.5">
          <label htmlFor={`${ids}-amount`} className="text-sm font-semibold">
            {editing.kind === "goal" ? "Keep each month (₹)" : "Each month (₹)"}
          </label>
          <Input
            id={`${ids}-amount`}
            inputMode="decimal"
            autoComplete="off"
            value={amount}
            aria-invalid={(amount !== "" && (paise === null || tooBig)) || undefined}
            onChange={(event) => setAmount(event.target.value)}
          />
        </div>
      </div>
      {problem && <ProblemNotice problem={problem} />}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || paise === null || tooBig}>
          <Check aria-hidden="true" /> {busy ? "Saving…" : "Save"}
        </Button>
        {removable && (
          <Button type="button" variant="outline" disabled={busy} onClick={() => void save(null)}>
            <Trash2 aria-hidden="true" /> Remove
          </Button>
        )}
        <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>
          <X aria-hidden="true" /> Cancel
        </Button>
      </div>
    </form>
  );
}

/** Monthly budgets and the savings goal, against this period's confirmed spending. Reports holds
 *  the full editor; Home shows a compact snapshot (the three fullest budgets) that links to it. */
export function BudgetsCard({
  period,
  version,
  compact = false,
}: {
  period: Period;
  version: number;
  compact?: boolean;
}) {
  const budgets = useResource(`budgets:${period ? `${period.year}-${period.month}` : "current"}:${version}`, (signal) =>
    getBudgets(period, signal),
  );
  const [editing, setEditing] = useState<Editing>(null);
  const plan = budgets.stale ? null : budgets.data;
  const canAdd = plan ? plan.categories.some((category) => !plan.items.some((item) => item.category === category)) : false;
  const reports = `/reports${period ? `?year=${period.year}&month=${period.month}` : ""}#budgets`;
  const items = plan
    ? compact
      ? [...plan.items].sort((a, b) => b.spent_minor / b.limit_minor - a.spent_minor / a.limit_minor).slice(0, 3)
      : plan.items
    : [];
  return (
    <section id={compact ? undefined : "budgets"} aria-labelledby="budgets-title" className="surface scroll-mt-24 rounded-3xl p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="budgets-title" className="text-lg font-semibold">Budgets</h2>
        {compact ? (
          <Link href={reports} className="inline-flex items-center gap-0.5 text-sm font-semibold text-ink underline-offset-4 hover:underline">
            All budgets <ChevronRight className="size-4" aria-hidden="true" />
          </Link>
        ) : (
          plan &&
          canAdd &&
          editing === null && (
            <Button variant="ghost" size="sm" onClick={() => setEditing({ kind: "budget", category: null })}>
              <Plus aria-hidden="true" /> Add a budget
            </Button>
          )
        )}
      </div>
      {!compact && (
        <p className="mt-1 text-xs text-ink-soft">
          {period ? `${monthLabel(period.year, period.month)} · ` : "This month · "}FinBoy warns you on WhatsApp from 80%.
        </p>
      )}
      {budgets.status === "loading" && <LoadingPanel className="mt-3 shadow-none" label="Loading budgets…" />}
      <RefreshingLabel active={budgets.status === "refreshing"}>Updating…</RefreshingLabel>
      {budgets.error !== null && (
        <ProblemNotice className="mt-3" problem={describeProblem(budgets.error, "Budgets couldn't be loaded")} onRetry={budgets.reload} />
      )}
      {plan && (
        <>
          {editing && !compact && (
            <EditForm
              key={editing.kind === "budget" ? `budget:${editing.category ?? "new"}` : "goal"}
              plan={plan}
              editing={editing}
              onCancel={() => setEditing(null)}
              onSaved={(next) => {
                // A change answers with this month's figures; another month is fetched again.
                if (period) budgets.reload();
                else budgets.replace(next);
                setEditing(null);
              }}
            />
          )}
          {items.length > 0 ? (
            <ul className="mt-2 divide-y">
              {items.map((item) => (
                <BudgetRow
                  key={item.category}
                  item={item}
                  onEdit={compact ? undefined : () => setEditing({ kind: "budget", category: item.category })}
                />
              ))}
            </ul>
          ) : (
            editing === null && (
              <p className="mt-4 text-sm text-ink-soft">
                {compact ? (
                  <>
                    No budgets yet.{" "}
                    <Link href={reports} className="font-semibold text-ink underline underline-offset-4">
                      Set one in Reports
                    </Link>
                    , or send &ldquo;food budget 5000&rdquo; to FinBoy on WhatsApp.
                  </>
                ) : (
                  <>No budgets yet. Add one here, or send &ldquo;food budget 5000&rdquo; to FinBoy on WhatsApp.</>
                )}
              </p>
            )
          )}
          {(!compact || plan.goal_minor !== null) && (
            <div className="mt-4 border-t pt-4">
              <Goal plan={plan} onEdit={compact ? undefined : () => setEditing({ kind: "goal" })} />
            </div>
          )}
        </>
      )}
    </section>
  );
}
