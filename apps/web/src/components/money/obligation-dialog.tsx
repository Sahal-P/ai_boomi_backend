"use client";

import { X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useId, useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useResource } from "@/hooks/use-resource";
import {
  formatMoney,
  getObligation,
  inputPaise,
  rupeeInput,
  updateObligation,
  type ObligationChange,
  type ObligationDetail,
} from "@/lib/api/money";
import { formatDay, formatDayTime } from "@/lib/dates";
import { liabilityLabels, obligationKindLabels, sourceLabels, sourceSender } from "@/lib/labels";
import { describeProblem, isConflict } from "@/lib/messages";

function ObligationBody({ detail, onChanged }: { detail: ObligationDetail; onChanged: (next: ObligationDetail) => void }) {
  const item = detail.commitment;
  const action = useAction();
  const ids = useId();
  const [label, setLabel] = useState(item.label);
  const [amount, setAmount] = useState(rupeeInput(item.amount_minor));
  const [due, setDue] = useState(item.due_date);
  const [invalid, setInvalid] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [seen, setSeen] = useState(detail.version);
  if (seen !== detail.version) {
    // A saved change returns the server's obligation; show its values in the form.
    setSeen(detail.version);
    setLabel(item.label);
    setAmount(rupeeInput(item.amount_minor));
    setDue(item.due_date);
  }
  const parsed = inputPaise(amount);
  const dirty = label.trim() !== item.label || parsed !== item.amount_minor || due !== item.due_date;
  const resolved = item.liability_state === "paid" || item.liability_state === "dismissed";

  async function change(update: Omit<ObligationChange, "expected_version">, done: string) {
    setMessage(null);
    const next = await action.run("update", "The obligation wasn't updated", () =>
      updateObligation(item.id, { expected_version: detail.version, ...update }),
    );
    if (next) {
      onChanged(next);
      setMessage(done);
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs font-semibold text-ink-soft">
          {obligationKindLabels[item.kind]} · {liabilityLabels[item.liability_state]}
        </p>
        <h2 className="mt-1 text-xl font-semibold break-words">{item.label}</h2>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{formatMoney(item.amount_minor)}</p>
        <p className="mt-1 text-sm text-ink-soft">
          {item.liability_state === "overdue" ? "Was due" : "Due"} {formatDay(item.due_date)}
        </p>
      </header>
      <p className="rounded-2xl bg-ink/[0.04] p-4 text-sm leading-relaxed">
        {resolved
          ? "This obligation is resolved, so it isn't deducted from your estimate."
          : item.liability_state === "overdue"
            ? "It's past its due date and still unpaid in your records, so it stays deducted from your estimate until you mark it paid or dismiss it."
            : "It's deducted from your estimate until it's paid or dismissed."}
        {item.uncertain && !resolved && " FinBoy isn't sure this bill is real or correct, so it's deducted conservatively until you check it."}
      </p>

      {!resolved && (
        <div className="flex flex-wrap gap-2">
          <Button disabled={action.busy !== null || dirty} onClick={() => void change({ status: "paid" }, "Marked as paid. It's no longer deducted.")}>
            I&apos;ve paid this
          </Button>
          <Button variant="outline" disabled={action.busy !== null || dirty} onClick={() => void change({ status: "dismissed" }, "Dismissed. It's no longer deducted.")}>
            Not a real bill — dismiss
          </Button>
        </div>
      )}
      {resolved && (
        <Button variant="outline" disabled={action.busy !== null} onClick={() => void change({ status: "upcoming" }, "Reopened. It's deducted again until resolved.")}>
          Reopen
        </Button>
      )}

      {!resolved && (
        <form
          noValidate
          className="space-y-3 border-t pt-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!label.trim() || parsed === null || !/^\d{4}-\d{2}-\d{2}$/.test(due)) {
              setInvalid(true);
              return;
            }
            setInvalid(false);
            const update: Omit<ObligationChange, "expected_version"> = {};
            if (label.trim() !== item.label) update.label = label.trim();
            if (parsed !== item.amount_minor) update.amount_minor = parsed;
            if (due !== item.due_date) update.due_date = due;
            void change(update, "Saved. The estimate uses the corrected obligation.");
          }}
        >
          <h3 className="font-semibold">Correct it</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="sm:col-span-3">
              <label htmlFor={`${ids}-label`} className="text-xs font-semibold">Name</label>
              <input id={`${ids}-label`} value={label} maxLength={120} onChange={(event) => setLabel(event.target.value)} className="mt-1.5 block h-11 w-full rounded-xl border border-input px-3 text-sm" />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor={`${ids}-amount`} className="text-xs font-semibold">Amount (₹)</label>
              <input id={`${ids}-amount`} value={amount} inputMode="decimal" aria-invalid={(invalid && parsed === null) || undefined} onChange={(event) => setAmount(event.target.value)} className="mt-1.5 block h-11 w-full rounded-xl border border-input px-3 text-sm tabular-nums aria-invalid:border-destructive" />
            </div>
            <div>
              <label htmlFor={`${ids}-due`} className="text-xs font-semibold">Due date</label>
              <input id={`${ids}-due`} type="date" value={due} onChange={(event) => setDue(event.target.value)} className="mt-1.5 block h-11 w-full rounded-xl border border-input px-3 text-sm" />
            </div>
          </div>
          {invalid && (
            <p role="alert" className="text-xs font-medium text-destructive">
              Use a name, a positive amount and a due date. Nothing was saved.
            </p>
          )}
          {dirty && (
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={action.busy !== null}>Save correction</Button>
              <Button type="button" variant="ghost" onClick={() => { setLabel(item.label); setAmount(rupeeInput(item.amount_minor)); setDue(item.due_date); setInvalid(false); }}>
                Discard changes
              </Button>
            </div>
          )}
        </form>
      )}

      <div role="status" aria-live="polite">
        {message && <p className="rounded-2xl bg-white/60 px-4 py-3 text-sm font-medium">{message}</p>}
      </div>
      {action.problem && (
        <ProblemNotice problem={action.problem}>
          {isConflict(action.lastError) && <p className="mt-1">Close and reopen it to see the latest version.</p>}
        </ProblemNotice>
      )}

      <section>
        <h3 className="font-semibold">Evidence</h3>
        {!detail.sources.length ? (
          <p className="mt-1 text-sm text-ink-soft">
            {item.kind === "loan"
              ? "You told FinBoy about this due on WhatsApp. No email is linked."
              : "No source email is linked to this obligation."}
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {detail.sources.map((source) => (
              <li key={source.id} className="rounded-2xl border p-3 text-sm">
                <p className="font-semibold break-all">{sourceSender(source)}</p>
                <p className="text-xs text-ink-soft">
                  {sourceLabels[source.source]} · received {formatDayTime(source.received_at)}
                  {source.due_date ? ` · due ${formatDay(source.due_date)}` : ""} · {formatMoney(source.amount_minor)}
                </p>
                {Object.entries(source.evidence).map(([key, value]) => (
                  <p key={key} className="mt-1 text-xs break-words">&ldquo;{value}&rdquo;</p>
                ))}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Inspect and resolve one obligation that the estimate deducts. */
export function ObligationDialog({
  id,
  onClose,
  onChanged,
}: {
  id: string | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const detail = useResource(id ? `obligation:${id}` : null, (signal) => getObligation(id ?? "", signal));
  const data = detail.stale ? null : detail.data;
  return (
    <Dialog.Root open={id !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/20 backdrop-blur-sm" />
        <Dialog.Content
          aria-describedby={undefined}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (id) document.querySelector<HTMLElement>(`[data-obligation-id="${CSS.escape(id)}"]`)?.focus();
          }}
          className="fixed inset-x-0 bottom-0 z-50 max-h-[94dvh] overflow-y-auto rounded-t-3xl float-panel p-5 pb-8 sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:max-h-[90dvh] sm:w-[calc(100%-2rem)] sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:p-7"
        >
          <Dialog.Title className="sr-only">Obligation details</Dialog.Title>
          <div className="mb-2 flex justify-end">
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close obligation">
                <X className="size-5" aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </div>
          {detail.status === "loading" && <LoadingPanel className="shadow-none" label="Loading this obligation…" />}
          {detail.error !== null && !data && (
            <ProblemNotice
              problem={describeProblem(detail.error, "This obligation couldn't be loaded")}
              onRetry={detail.reload}
            />
          )}
          {data && (
            <ObligationBody
              key={data.commitment.id}
              detail={data}
              onChanged={(next) => {
                detail.replace(next);
                onChanged();
              }}
            />
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
