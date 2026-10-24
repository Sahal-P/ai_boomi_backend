"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  categories,
  inputPaise,
  kinds,
  rupeeInput,
  type Category,
  type Kind,
  type Transaction,
} from "@/lib/api/money";
import type { Correction } from "@/lib/api/transactions";
import { istDate, withIstDate } from "@/lib/dates";
import { readDraft, writeDraft, type CorrectionDraft } from "@/lib/drafts";
import { categoryLabels, kindLabels } from "@/lib/labels";
import { setUnsaved } from "@/lib/unsaved-work";
import { cn } from "@/lib/utils";

const MONEY_IN: readonly Kind[] = ["salary", "income_other", "refund", "reversal"];
const MONEY_OUT: readonly Kind[] = ["purchase", "fee", "bill_payment", "emi"];

export function draftFrom(tx: Transaction): CorrectionDraft {
  return {
    merchant: tx.merchant,
    amount: rupeeInput(tx.amount_minor),
    category: tx.category,
    date: istDate(tx.occurred_at),
    direction: tx.direction,
    kind: tx.kind,
  };
}

type Errors = Partial<Record<keyof CorrectionDraft, string>>;

function latestDate(evidence: string): string {
  const today = istDate(new Date());
  return evidence > today ? evidence : today;
}

function validate(draft: CorrectionDraft, baseline: CorrectionDraft): { errors: Errors; amount: number | null } {
  const errors: Errors = {};
  const amount = inputPaise(draft.amount);
  if (!draft.merchant.trim()) errors.merchant = "Enter the merchant or payer name.";
  else if (draft.merchant.trim().length > 160) errors.merchant = "Use at most 160 characters.";
  if (amount === null) errors.amount = "Enter a positive amount in rupees, with at most two decimals.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date)) errors.date = "Choose a date.";
  // Evidence can carry a later date (a scheduled debit); only a date the person typed is checked.
  else if (draft.date !== baseline.date && draft.date > istDate(new Date())) {
    errors.date = "The date can't be in the future.";
  }
  const kind = draft.kind as Kind;
  if (MONEY_IN.includes(kind) && draft.direction !== "in") {
    errors.direction = `${kindLabels[kind]} is money coming in. Change the direction or the type.`;
  } else if (MONEY_OUT.includes(kind) && draft.direction !== "out") {
    errors.direction = `${kindLabels[kind]} is money going out. Change the direction or the type.`;
  }
  return { errors, amount };
}

function changes(tx: Transaction, draft: CorrectionDraft, amount: number | null): Correction {
  const result: Correction = {};
  if (draft.merchant.trim() !== tx.merchant) result.merchant = draft.merchant.trim();
  if (amount !== null && amount !== tx.amount_minor) result.amount_minor = amount;
  if (draft.category !== tx.category) result.category = draft.category as Category;
  if (draft.date !== istDate(tx.occurred_at)) result.occurred_at = withIstDate(tx.occurred_at, draft.date);
  if (draft.direction !== tx.direction) result.direction = draft.direction;
  if (draft.kind !== tx.kind) result.kind = draft.kind as Kind;
  return result;
}

export type FormSubmit = (intent: "save" | "save_confirm", correction: Correction) => Promise<boolean>;

/**
 * Editable record facts with one unambiguous decision model: edits are either saved alone or
 * saved and confirmed atomically; a dirty draft disables contradictory actions elsewhere.
 */
export function CorrectionForm({
  tx,
  editable,
  canConfirm,
  busy,
  onSubmit,
  onDirtyChange,
}: {
  tx: Transaction;
  editable: boolean;
  canConfirm: boolean;
  busy: boolean;
  onSubmit: FormSubmit;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const baseline = useMemo(() => draftFrom(tx), [tx]);
  const [draft, setDraft] = useState<CorrectionDraft>(() => readDraft(tx.id) ?? baseline);
  const [restored] = useState(() => readDraft(tx.id) !== undefined);
  const [showErrors, setShowErrors] = useState(false);
  const prefix = useId();
  const ids = {
    merchant: `${prefix}-merchant`,
    amount: `${prefix}-amount`,
    category: `${prefix}-category`,
    date: `${prefix}-date`,
    direction: `${prefix}-direction`,
    kind: `${prefix}-kind`,
  };
  const dirty = (Object.keys(baseline) as (keyof CorrectionDraft)[]).some((key) => draft[key] !== baseline[key]);
  const { errors, amount } = validate(draft, baseline);
  const invalid = Object.keys(errors).length > 0;

  useEffect(() => {
    setUnsaved(`record:${tx.id}`, dirty);
    onDirtyChange(dirty);
  }, [tx.id, dirty, onDirtyChange]);
  useEffect(() => () => setUnsaved(`record:${tx.id}`, false), [tx.id]);

  function update<K extends keyof CorrectionDraft>(key: K, value: CorrectionDraft[K]) {
    const next = { ...draft, [key]: value };
    setDraft(next);
    const stillDirty = (Object.keys(baseline) as (keyof CorrectionDraft)[]).some((field) => next[field] !== baseline[field]);
    writeDraft(tx.id, stillDirty ? next : null);
  }

  function discard() {
    setDraft(baseline);
    setShowErrors(false);
    writeDraft(tx.id, null);
  }

  async function submit(intent: "save" | "save_confirm") {
    if (invalid) {
      setShowErrors(true);
      return;
    }
    const correction = changes(tx, draft, amount);
    if (intent === "save" && !Object.keys(correction).length) return;
    const ok = await onSubmit(intent, correction);
    if (ok) {
      writeDraft(tx.id, null);
      setShowErrors(false);
    }
  }

  // After a save the server's record becomes the new baseline; adopt it when the draft matches nothing new.
  const [lastBaseline, setLastBaseline] = useState(baseline);
  if (lastBaseline !== baseline) {
    setLastBaseline(baseline);
    if (!readDraft(tx.id)) setDraft(baseline);
  }

  const field = (key: keyof CorrectionDraft) => ({
    "aria-invalid": showErrors && errors[key] ? true : undefined,
    "aria-describedby": showErrors && errors[key] ? `${ids[key]}-error` : undefined,
  });
  const fieldError = (key: keyof CorrectionDraft) =>
    showErrors && errors[key] ? (
      <p id={`${ids[key]}-error`} className="mt-1 text-xs font-medium text-destructive">
        {errors[key]}
      </p>
    ) : null;
  const inputClass =
    "mt-1.5 block h-11 w-full rounded-xl border border-input bg-white px-3 text-sm disabled:bg-muted disabled:text-ink-soft aria-invalid:border-destructive";

  return (
    <form
      noValidate
      aria-label="Record details"
      onSubmit={(event) => {
        event.preventDefault();
        void submit(canConfirm ? "save_confirm" : "save");
      }}
    >
      {restored && dirty && (
        <p role="status" className="mb-3 rounded-xl bg-lilac/60 px-3 py-2 text-xs font-medium text-ink">
          Your unsaved changes to this record were restored.
        </p>
      )}
      <fieldset disabled={!editable || busy} className="grid gap-3 sm:grid-cols-2">
        <legend className="sr-only">Correct this record</legend>
        <div className="sm:col-span-2">
          <label htmlFor={ids.merchant} className="text-xs font-semibold">Merchant or payer</label>
          <input id={ids.merchant} value={draft.merchant} maxLength={160} onChange={(event) => update("merchant", event.target.value)} className={inputClass} {...field("merchant")} />
          {fieldError("merchant")}
        </div>
        <div>
          <label htmlFor={ids.amount} className="text-xs font-semibold">Amount (₹)</label>
          <input id={ids.amount} value={draft.amount} inputMode="decimal" onChange={(event) => update("amount", event.target.value)} className={cn(inputClass, "tabular-nums")} {...field("amount")} />
          {fieldError("amount")}
        </div>
        <div>
          <label htmlFor={ids.date} className="text-xs font-semibold">Date</label>
          <input id={ids.date} type="date" value={draft.date} max={latestDate(baseline.date)} onChange={(event) => update("date", event.target.value)} className={inputClass} {...field("date")} />
          {fieldError("date")}
        </div>
        <div>
          <label htmlFor={ids.direction} className="text-xs font-semibold">Direction</label>
          <select id={ids.direction} value={draft.direction} onChange={(event) => update("direction", event.target.value === "in" ? "in" : "out")} className={inputClass} {...field("direction")}>
            <option value="out">Money out</option>
            <option value="in">Money in</option>
          </select>
          {fieldError("direction")}
        </div>
        <div>
          <label htmlFor={ids.kind} className="text-xs font-semibold">Type</label>
          <select id={ids.kind} value={draft.kind} onChange={(event) => update("kind", event.target.value)} className={inputClass} {...field("kind")}>
            {kinds.map((value) => (
              <option key={value} value={value}>{kindLabels[value]}</option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-2">
          <label htmlFor={ids.category} className="text-xs font-semibold">Category</label>
          <select id={ids.category} value={draft.category} onChange={(event) => update("category", event.target.value)} className={inputClass}>
            {categories.map((value) => (
              <option key={value} value={value}>{categoryLabels[value]}</option>
            ))}
          </select>
        </div>
      </fieldset>
      {editable && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {canConfirm ? (
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : dirty ? "Save and confirm" : "Confirm"}
            </Button>
          ) : (
            dirty && (
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save correction"}
              </Button>
            )
          )}
          {canConfirm && dirty && (
            <Button type="button" variant="outline" disabled={busy} onClick={() => void submit("save")}>
              Save without confirming
            </Button>
          )}
          {dirty && (
            <Button type="button" variant="ghost" disabled={busy} onClick={discard}>
              Discard changes
            </Button>
          )}
        </div>
      )}
      {showErrors && invalid && (
        <p role="alert" className="mt-2 text-xs font-medium text-destructive">
          Fix the highlighted fields — nothing was saved.
        </p>
      )}
    </form>
  );
}
