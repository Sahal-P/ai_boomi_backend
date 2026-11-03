"use client";

import { Check } from "lucide-react";
import { useId, useRef, useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { Progress } from "@/components/ui/progress";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useResource } from "@/hooks/use-resource";
import {
  categories,
  formatMoney,
  getPayees,
  periodQuery,
  sortPayee,
  type Category,
  type Period,
} from "@/lib/api/money";
import { sharePercent } from "@/lib/charts";
import { categoryLabels } from "@/lib/labels";
import { describeProblem, hasCode, type Problem } from "@/lib/messages";
import { emitRecordsChanged } from "@/lib/record-events";

// Income categories belong to money received; "Other" is what this sheet sorts away from.
const INCOME = new Set<Category>(["salary", "other_income", "wages", "farm_sales", "govt_benefit"]);
const CHOICES = categories.filter((category) => !INCOME.has(category) && category !== "other");
const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

function PayeeSorter({ period, label, onChanged }: { period: Period; label: string; onChanged: () => void }) {
  const ids = useId();
  const payees = useResource(`payees:${JSON.stringify(periodQuery(period))}`, (signal) => getPayees(period, signal));
  const [chosen, setChosen] = useState<Record<string, Category>>({});
  const [sortedMinor, setSortedMinor] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  // Each sort returns the next version; until then the list's own version applies.
  const [latest, setLatest] = useState<string | null>(null);
  const data = payees.stale ? null : payees.data;
  const version = latest ?? data?.data_version ?? null;

  async function choose(name: string, amount: number, category: Category) {
    if (!version || busy) return;
    setBusy(name);
    setProblem(null);
    try {
      const result = await sortPayee(name, category, version);
      setLatest(result.data_version);
      setSortedMinor((value) => value + (name in chosen ? 0 : amount));
      setChosen((current) => ({ ...current, [name]: category }));
      onChanged();
    } catch (error) {
      setProblem(describeProblem(error, `${name} wasn't sorted`));
      if (hasCode(error, "version_conflict")) {
        // Records changed elsewhere; start again from the latest list.
        setLatest(null);
        setChosen({});
        setSortedMinor(0);
        payees.reload();
      }
    } finally {
      setBusy(null);
    }
  }

  if (payees.status === "loading") return <LoadingPanel className="mt-5 shadow-none" label="Finding payees to sort…" />;
  if (payees.error !== null)
    return (
      <ProblemNotice
        className="mt-5"
        problem={describeProblem(payees.error, "Payees couldn't be loaded")}
        onRetry={payees.reload}
      />
    );
  if (!data) return null;
  const sorted = data.spent_minor ? (data.spent_minor - data.unsorted_minor + sortedMinor) / data.spent_minor : 1;
  return (
    <div className="mt-5 space-y-4">
      <div>
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="font-semibold">{sharePercent(Math.min(1, sorted))} of spending sorted</span>
          <span className="text-xs text-ink-soft">{label}</span>
        </div>
        <Progress value={Math.round(Math.min(1, sorted) * 100)} aria-label="Spending sorted into categories" className="mt-2 h-1.5" />
      </div>
      {problem && <ProblemNotice problem={problem} />}
      {data.items.length === 0 ? (
        <p className="rounded-2xl bg-well p-4 text-sm ring-1 ring-ink/5">Every payee in {label} has a category.</p>
      ) : (
        <ul className="divide-y" aria-label="Payees to sort">
          {data.items.map((payee, index) => {
            // Names have spaces, which an id can't.
            const id = `${ids}-${index}`;
            const done = chosen[payee.name];
            return (
              <li key={payee.name} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
                <div className="min-w-0 flex-1 basis-40">
                  <label htmlFor={id} className="block truncate text-sm font-semibold">
                    {payee.name}
                  </label>
                  <p className="text-xs text-ink-soft tabular-nums">
                    {plural(payee.count, "payment", "payments")} · {formatMoney(payee.amount_minor)}
                  </p>
                </div>
                <div className="flex w-full items-center gap-2 sm:w-48">
                  {done && <Check className="size-4 shrink-0 text-positive" aria-label="Sorted" />}
                  <select
                    id={id}
                    value={done ?? ""}
                    disabled={busy !== null}
                    onChange={(event) => {
                      const value = event.target.value as Category;
                      if (value) void choose(payee.name, payee.amount_minor, value);
                    }}
                    className="field field-select h-11 w-full min-w-0 rounded-lg pl-3 text-sm"
                  >
                    <option value="" disabled>
                      {busy === payee.name ? "Saving…" : "Choose a category"}
                    </option>
                    {CHOICES.map((category) => (
                      <option key={category} value={category}>
                        {categoryLabels[category]}
                      </option>
                    ))}
                  </select>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/**
 * Sort payees once: a category for every payment to a payee, past and future (merchant memory).
 * The list is the period's spending still under "Other", largest first.
 */
export function SortPayees({
  open,
  onOpenChange,
  period,
  label,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  period: Period;
  label: string;
}) {
  const wide = useMediaQuery("(min-width: 640px)");
  const changed = useRef(false);
  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next && changed.current) {
          changed.current = false;
          emitRecordsChanged();
        }
      }}
    >
      <SheetContent side={wide ? "right" : "bottom"} className="gap-0 overflow-y-auto p-5 data-[side=bottom]:max-h-[92dvh] sm:max-w-md sm:p-6">
        <SheetHeader className="p-0">
          <SheetTitle className="text-xl">Sort payees</SheetTitle>
          <SheetDescription>
            Choose a category once and every payment to that payee follows — past ones and the next ones. Biggest
            first.
          </SheetDescription>
        </SheetHeader>
        {open && <PayeeSorter period={period} label={label} onChanged={() => (changed.current = true)} />}
      </SheetContent>
    </Sheet>
  );
}
