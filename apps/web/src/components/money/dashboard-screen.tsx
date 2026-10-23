"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  CalendarClock,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { SceneSlot } from "@/components/three/scene-slot";
import {
  formatMoney,
  inputPaise,
  label,
  recordsNote,
  simulationDisclaimer,
  type MoneySummary,
  type Commitment,
  type Simulation,
} from "@/lib/api/money";

export function DashboardScreen({
  data,
  error,
  refresh,
  simulation,
  busy,
  onSimulate,
}: {
  data: { summary: MoneySummary; commitments: Commitment[] } | null;
  error: string | null;
  refresh: () => void;
  simulation: Simulation | null;
  busy: boolean;
  onSimulate: (amount: number) => void;
}) {
  const [amount, setAmount] = useState("5000");
  const [validation, setValidation] = useState<string | null>(null);
  const summary = data?.summary;
  return (
    <div className="space-y-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow text-violet">Your money, a little clearer</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            The bigger picture.
          </h1>
          <p className="mt-3 text-sm text-ink-soft">
            {summary
              ? `${summary.period_start} — ${summary.period_end} · As of ${summary.as_of}`
              : "Checking your tracked records…"}
          </p>
        </div>
        <Button variant="outline" onClick={refresh}>
          <RefreshCw className="size-4" /> Refresh
        </Button>
      </header>
      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
        >
          {error}{" "}
          <button onClick={refresh} className="underline">
            Try again
          </button>
        </div>
      )}
      {!data && !error && (
        <div role="status" className="surface rounded-3xl p-8">
          Loading your money summary…
        </div>
      )}
      {summary && (
        <>
          {!summary.income_transaction_count &&
            !summary.outflow_transaction_count && (
              <div className="surface rounded-3xl p-7">
                <h2 className="text-xl font-semibold">
                  Start with your email trail.
                </h2>
                <p className="mt-3 text-sm text-ink-soft">
                  Import a demo mailbox, connect Gmail, or upload .eml files to
                  build your tracked records.
                </p>
                <Button asChild className="mt-5">
                  <Link href="/connect">Choose an import mode</Link>
                </Button>
              </div>
            )}
          <section className="relative overflow-hidden rounded-[2rem] bg-ink p-6 text-white sm:p-9">
            <div className="relative z-20 max-w-lg">
              <p className="text-sm text-white/70">
                Estimated unallocated amount
              </p>
              <p className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
                {formatMoney(summary.estimated_unallocated_minor)}
              </p>
              <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/70">
                {recordsNote}
              </p>
              <Button asChild className="mt-6 bg-white text-ink hover:bg-lilac">
                <Link href="/assistant">
                  <Sparkles className="size-4" /> Ask about my money
                </Link>
              </Button>
            </div>
            <SceneSlot
              spec={{ name: "coin-swirl", merge: 1 }}
              className="pointer-events-none absolute top-0 right-0 hidden h-full w-1/2 opacity-70 md:block"
            />
          </section>
          <dl className="grid gap-4 sm:grid-cols-3">
            {[
              {
                name: "Tracked income",
                value: summary.tracked_income_minor,
                Icon: ArrowDownLeft,
                color: "text-positive",
              },
              {
                name: "Confirmed net outflows",
                value: summary.confirmed_outflows_minor,
                Icon: ArrowUpRight,
                color: "text-violet",
              },
              {
                name: "Upcoming commitments",
                value: summary.upcoming_commitments_minor,
                Icon: CalendarClock,
                color: "text-warning",
              },
            ].map(({ name, value, Icon, color }) => (
              <div key={name} className="surface rounded-3xl p-5">
                <Icon className={`mb-5 size-5 ${color}`} />
                <dt className="text-xs text-ink-soft">{name}</dt>
                <dd className="mt-2 text-2xl font-semibold tracking-tight">
                  {formatMoney(value)}
                </dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-5 xl:grid-cols-2">
            <section className="surface rounded-3xl p-6">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold">Where it went</h2>
                <Link
                  href="/transactions"
                  className="text-xs font-semibold text-violet"
                >
                  View transactions →
                </Link>
              </div>
              <ul className="mt-7 space-y-5">
                {summary.categories
                  .filter((item) => item.amount_minor !== 0)
                  .map((item) => (
                    <li key={item.category}>
                      <div className="flex justify-between gap-4 text-sm">
                        <span>{label(item.category)}</span>
                        <strong className="tabular-nums">
                          {formatMoney(item.amount_minor)}
                        </strong>
                      </div>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-violet"
                          style={{
                            width: `${Math.min(100, Math.max(2, (Math.abs(item.amount_minor) / Math.max(...summary.categories.map((row) => Math.abs(row.amount_minor)), 1)) * 100))}%`,
                          }}
                        />
                      </div>
                    </li>
                  ))}
              </ul>
              {!summary.categories.length && (
                <p className="mt-5 text-sm text-ink-soft">
                  No confirmed spending yet.
                </p>
              )}
            </section>
            <section className="surface rounded-3xl p-6">
              <h2 className="text-lg font-semibold">Coming up</h2>
              <ul className="mt-6 divide-y">
                {data.commitments.map((item) => (
                  <li key={item.id} className="flex justify-between gap-4 py-4">
                    <div>
                      <p className="text-sm font-medium">{item.label}</p>
                      <p className="mt-1 text-xs text-ink-soft">
                        Due {item.due_date} · {label(item.kind)}
                      </p>
                    </div>
                    <strong className="text-sm tabular-nums">
                      {formatMoney(item.amount_minor)}
                    </strong>
                  </li>
                ))}
              </ul>
              {!data.commitments.length && (
                <p className="mt-6 text-sm text-ink-soft">
                  No upcoming commitments in the tracked records.
                </p>
              )}
              <div className="mt-7 rounded-2xl bg-lilac/60 p-4 text-sm">
                <strong>
                  {summary.pending_review_count} items need a human look.
                </strong>
                <p className="mt-2 text-ink-soft">
                  Unconfirmed records stay out of your totals.
                </p>
                <Link
                  href="/review"
                  className="mt-3 inline-block font-semibold text-violet"
                >
                  Open review →
                </Link>
              </div>
            </section>
          </div>
          <section className="surface rounded-3xl p-6 sm:p-8">
            <div className="max-w-xl">
              <p className="eyebrow text-violet">
                A question, not a recommendation
              </p>
              <h2 className="mt-2 text-2xl font-semibold">
                What if I set some money aside?
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-ink-soft">
                Model a monthly commitment using tracked income, confirmed
                spending, and upcoming bills.
              </p>
            </div>
            <form
              className="mt-6 flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                const parsed = inputPaise(amount);
                if (parsed === null) {
                  setValidation(
                    "Enter a positive rupee amount with up to two decimal places.",
                  );
                  return;
                }
                setValidation(null);
                onSimulate(parsed);
              }}
            >
              <div>
                <label
                  htmlFor="simulation-amount"
                  className="block text-sm font-medium"
                >
                  Monthly amount (₹)
                </label>
                <input
                  id="simulation-amount"
                  inputMode="decimal"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  className="mt-2 h-11 w-full max-w-64 rounded-xl border bg-background px-4"
                  required
                />
              </div>
              <Button type="submit" disabled={busy} className="h-11">
                {busy ? "Calculating…" : "Model cash flow"}
              </Button>
            </form>
            {validation && (
              <p role="alert" className="mt-3 text-sm text-destructive">
                {validation}
              </p>
            )}
            {simulation && (
              <div className="mt-6 rounded-2xl bg-lilac/50 p-5">
                <dl className="space-y-3">
                  {simulation.lines.map((line) => (
                    <div
                      key={line.label_key}
                      className="flex justify-between gap-4 text-sm"
                    >
                      <dt>{label(line.label_key)}</dt>
                      <dd>
                        {line.sign} {formatMoney(line.amount_minor)}
                      </dd>
                    </div>
                  ))}
                </dl>
                <div className="mt-5 flex flex-wrap justify-between gap-3 border-t pt-5">
                  <p>Estimated remaining</p>
                  <strong className="text-2xl text-violet">
                    {formatMoney(simulation.remaining_after_proposal_minor)}
                  </strong>
                </div>
                <ul className="mt-4 space-y-1 text-xs text-ink-soft">
                  {simulation.warnings.map((warning) => (
                    <li key={warning}>{label(warning)}</li>
                  ))}
                </ul>
                <p className="mt-5 text-xs leading-relaxed">
                  {simulationDisclaimer}
                </p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
