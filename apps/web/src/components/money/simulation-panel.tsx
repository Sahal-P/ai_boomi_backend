"use client";

import { useId, useRef, useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { isAbort } from "@/lib/api/http";
import {
  formatMoney,
  inputPaise,
  simulate,
  simulationDisclaimer,
  type MoneySummary,
  type Simulation,
} from "@/lib/api/money";
import { formatDay } from "@/lib/dates";
import { simulationLineLabels, simulationWarningLabels } from "@/lib/labels";
import { describeProblem, type Problem } from "@/lib/messages";
import { cn } from "@/lib/utils";

/**
 * "What if I set money aside?" A result is always shown with the amount and data snapshot it
 * was calculated for, and is marked out of date when either changes. Arithmetic is the API's.
 */
export function SimulationPanel({ current }: { current: MoneySummary | null }) {
  const [amount, setAmount] = useState("5000");
  const [result, setResult] = useState<Simulation | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [invalid, setInvalid] = useState(false);
  const control = useRef<AbortController | null>(null);
  const inputId = useId();
  const errorId = useId();

  const typed = inputPaise(amount);
  const inputChanged = result !== null && typed !== result.proposed_monthly_minor;
  const recordsChanged =
    result !== null && current !== null && current.data_version !== result.summary.data_version;
  const stale = inputChanged || recordsChanged;

  async function run() {
    if (typed === null) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    control.current?.abort();
    const controller = new AbortController();
    control.current = controller;
    setBusy(true);
    setProblem(null);
    try {
      const next = await simulate(typed, controller.signal);
      if (!controller.signal.aborted) setResult(next);
    } catch (error) {
      if (!isAbort(error)) setProblem(describeProblem(error, "The calculation didn't run"));
    } finally {
      if (control.current === controller) {
        control.current = null;
        setBusy(false);
      }
    }
  }

  return (
    <section id="simulation" aria-labelledby="simulation-title" className="surface scroll-mt-24 rounded-3xl p-5 sm:p-7">
      <h2 id="simulation-title" className="text-lg font-semibold">
        What if I set money aside each month?
      </h2>
      <p className="mt-1 max-w-xl text-sm leading-relaxed text-ink-soft">
        Models this month&apos;s tracked income, confirmed spending and unresolved obligations. It
        isn&apos;t advice and doesn&apos;t move money.
      </p>
      <form
        className="mt-5 flex flex-wrap items-end gap-3"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void run();
        }}
      >
        <div>
          <label htmlFor={inputId} className="block text-sm font-medium">
            Monthly amount (₹)
          </label>
          <input
            id={inputId}
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            aria-invalid={invalid || undefined}
            aria-describedby={invalid ? errorId : undefined}
            className="mt-1.5 h-11 w-full max-w-56 rounded-xl border border-input bg-white px-4 tabular-nums aria-invalid:border-destructive"
          />
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? "Calculating…" : result && stale ? "Recalculate" : "Model cash flow"}
        </Button>
        {busy && (
          <Button type="button" variant="ghost" onClick={() => control.current?.abort()}>
            Cancel
          </Button>
        )}
      </form>
      {invalid && (
        <p id={errorId} role="alert" className="mt-2 text-sm font-medium text-destructive">
          Enter a positive rupee amount with up to two decimals, for example 5000 or 2500.50.
        </p>
      )}
      {problem && (
        <ProblemNotice className="mt-4" problem={problem} onRetry={() => void run()}>
          {result && <p className="mt-1">The result below is your last successful calculation.</p>}
        </ProblemNotice>
      )}
      {result && (
        <div
          className={cn(
            "mt-5 rounded-2xl bg-white/60 p-5 transition-opacity",
            stale && "opacity-70",
          )}
          aria-live="polite"
        >
          <p className="text-xs font-semibold text-ink-soft">
            Calculated for {formatMoney(result.proposed_monthly_minor)} a month, using your records
            as of {formatDay(result.summary.as_of)}.
          </p>
          {stale && (
            <p role="status" className="mt-2 rounded-xl bg-white px-3 py-2 text-sm font-semibold text-amber-900">
              Out of date —{" "}
              {inputChanged ? "you changed the amount" : "your records changed since"}. Recalculate
              to see the current result.
            </p>
          )}
          <dl className="mt-3 space-y-2">
            {result.lines.map((line) => (
              <div key={line.label_key} className="flex justify-between gap-4 text-sm">
                <dt>{simulationLineLabels[line.label_key]}</dt>
                <dd className="tabular-nums">
                  {line.sign === "+" ? "+" : "−"} {formatMoney(line.amount_minor)}
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-4 flex flex-wrap items-baseline justify-between gap-3 border-t border-ink/10 pt-4">
            <p className="text-sm font-medium">Estimated remaining</p>
            <strong className="text-2xl tracking-tight text-ink tabular-nums">
              {formatMoney(result.remaining_after_proposal_minor)}
            </strong>
          </div>
          {result.warnings.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-soft">
              {result.warnings.map((warning) => (
                <li key={warning}>{simulationWarningLabels[warning]}</li>
              ))}
            </ul>
          )}
          <p className="mt-4 text-xs leading-relaxed">{simulationDisclaimer}</p>
        </div>
      )}
    </section>
  );
}
