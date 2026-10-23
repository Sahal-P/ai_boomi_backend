"use client";
import { useState } from "react";
import Link from "next/link";
import { Dialog } from "radix-ui";
import {
  ArrowDownLeft,
  ArrowUpRight,
  FileCheck,
  RefreshCw,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  categories,
  categorySchema,
  formatMoney,
  inputPaise,
  label,
  recordsNote,
  type Transaction,
} from "@/lib/api/money";
import type { Correction, TransactionDetail } from "@/lib/api/transactions";

type Props = {
  rows: Transaction[] | null;
  detail: TransactionDetail | null;
  error: string | null;
  detailLoading: boolean;
  busy: boolean;
  query: string;
  setQuery: (value: string) => void;
  status: string;
  setStatus: (value: string) => void;
  refresh: () => void;
  inspect: (id: string) => void;
  close: () => void;
  mutate: (
    action: "correct" | "confirm" | "reject" | "merge" | "keep-separate",
    correction?: Correction,
    keepId?: string,
  ) => void;
  reviewOnly?: boolean;
};
export function TransactionsScreen(props: Props) {
  const { rows, detail, error, busy, reviewOnly } = props;
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow text-violet">
            {reviewOnly
              ? "You make the final call"
              : "An evidence-backed timeline"}
          </p>
          <h1 className="mt-2 text-3xl font-semibold">
            {reviewOnly ? "A second pair of eyes." : "Your money trail."}
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-ink-soft">
            {reviewOnly
              ? "FinBoy flags uncertainty. Confirm, correct, or reject a record after checking the evidence."
              : recordsNote}
          </p>
        </div>
        <Button variant="outline" onClick={props.refresh}>
          <RefreshCw className="size-4" />
          Refresh
        </Button>
      </header>
      {error && (
        <p
          role="alert"
          className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-950"
        >
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <label className="min-w-0 flex-1 text-xs font-medium">
          Find a merchant
          <input
            value={props.query}
            onChange={(event) => props.setQuery(event.target.value)}
            placeholder="Search your tracked records"
            className="mt-2 h-11 w-full rounded-xl border bg-white px-4 text-sm"
          />
        </label>
        {!reviewOnly && (
          <label className="text-xs font-medium">
            Record status
            <select
              value={props.status}
              onChange={(event) => props.setStatus(event.target.value)}
              className="mt-2 block h-11 rounded-xl border bg-white px-3 text-sm"
            >
              <option value="">All records</option>
              {[
                "confirmed",
                "needs_review",
                "rejected",
                "merged",
                "failed",
              ].map((status) => (
                <option key={status} value={status}>
                  {label(status)}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {!rows && !error && (
        <div role="status" className="surface rounded-3xl p-7">
          Loading records…
        </div>
      )}
      {rows && rows.length === 0 && (
        <div className="surface rounded-3xl p-8">
          <FileCheck className="size-8 text-violet" />
          <h2 className="mt-5 text-xl font-semibold">
            {reviewOnly
              ? "Nothing waiting for review."
              : "No matching records yet."}
          </h2>
          <p className="mt-3 text-sm text-ink-soft">
            {reviewOnly
              ? "Any uncertain records from your next import will appear here."
              : "Try another filter, or import your email trail."}
          </p>
          <Button asChild variant="outline" className="mt-5">
            <Link href="/connect">Import emails</Link>
          </Button>
        </div>
      )}
      {rows && rows.length > 0 && (
        <section className="surface overflow-hidden rounded-3xl">
          <ul className="divide-y">
            {rows.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => props.inspect(row.id)}
                  className="flex w-full items-center gap-3 px-4 py-5 text-left transition-colors hover:bg-lilac/30 sm:px-6"
                >
                  <span
                    className={`grid size-10 shrink-0 place-items-center rounded-2xl ${row.direction === "in" ? "bg-emerald-50 text-positive" : "bg-lilac text-violet"}`}
                  >
                    {row.direction === "in" ? (
                      <ArrowDownLeft className="size-5" />
                    ) : (
                      <ArrowUpRight className="size-5" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block break-words text-sm font-semibold">
                      {row.merchant}
                    </span>
                    <span className="mt-1 block text-xs text-ink-soft">
                      {label(row.category)} ·{" "}
                      {new Date(row.occurred_at).toLocaleDateString("en-IN", {
                        timeZone: "Asia/Kolkata",
                      })}
                    </span>
                    <span
                      className={`mt-2 inline-block rounded-full px-2 py-1 text-[10px] font-semibold ${row.status === "needs_review" ? "bg-amber-50 text-amber-900" : "bg-muted text-ink-soft"}`}
                    >
                      {label(row.status)}
                    </span>
                  </span>
                  <span className="shrink-0 text-right text-sm font-semibold tabular-nums">
                    {row.direction === "in" ? "+" : "−"}
                    {formatMoney(row.amount_minor)}
                    <span className="mt-2 block text-[10px] font-normal text-ink-soft">
                      See evidence →
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Dialog.Root
        open={Boolean(detail) || props.detailLoading}
        onOpenChange={(open) => {
          if (!open && !busy) props.close();
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/50 backdrop-blur-sm" />
          <Dialog.Content
            aria-describedby="transaction-description"
            className="fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100%-1.5rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-3xl bg-white p-5 shadow-lift sm:p-8"
          >
            <Dialog.Title className="pr-8 text-xl font-semibold">
              {detail?.transaction.merchant ?? "Loading evidence…"}
            </Dialog.Title>
            <Dialog.Description
              id="transaction-description"
              className="mt-2 text-xs leading-relaxed text-ink-soft"
            >
              Check source evidence before approving or changing a record.{" "}
              {recordsNote}
            </Dialog.Description>
            <Dialog.Close asChild>
              <button
                disabled={busy}
                aria-label="Close transaction"
                className="absolute top-5 right-5 p-1"
              >
                <X className="size-5" />
              </button>
            </Dialog.Close>
            {detail && (
              <DetailContent
                key={detail.transaction.id + detail.revisions.length}
                detail={detail}
                busy={busy}
                rows={rows ?? []}
                mutate={props.mutate}
              />
            )}{" "}
            {error && (
              <p role="alert" className="mt-4 text-sm text-destructive">
                {error}
              </p>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
function DetailContent({
  detail,
  busy,
  rows,
  mutate,
}: {
  detail: TransactionDetail;
  busy: boolean;
  rows: Transaction[];
  mutate: Props["mutate"];
}) {
  const tx = detail.transaction;
  const [category, setCategory] = useState(tx.category);
  const [merchant, setMerchant] = useState(tx.merchant);
  const [amount, setAmount] = useState((tx.amount_minor / 100).toFixed(2));
  const [keepId, setKeepId] = useState("");
  const [validation, setValidation] = useState("");
  return (
    <div className="mt-6 space-y-6">
      <div className="rounded-2xl bg-lilac/60 p-5">
        <p className="text-3xl font-semibold">{formatMoney(tx.amount_minor)}</p>
        <p className="mt-2 text-sm">
          {label(tx.status)} · {Math.round(tx.confidence * 100)}% evidence
          confidence
        </p>
        {tx.review_reason && (
          <p className="mt-3 text-sm text-amber-900">
            Needs your look: {label(tx.review_reason)}
          </p>
        )}
      </div>
      <section>
        <h3 className="font-semibold">Why FinBoy added this</h3>
        <p className="mt-2 text-xs text-ink-soft">
          {detail.sources.length} source notifications · source claims stay
          unchanged by your corrections.
        </p>
        <ul className="mt-4 space-y-3">
          {detail.sources.map((source) => (
            <li key={source.id} className="rounded-2xl border p-4">
              <p className="text-sm font-medium">
                {source.sender_domain} · {label(source.classification)}
              </p>
              <p className="mt-1 text-xs text-ink-soft">
                {label(source.source)} · {label(source.extraction_method)}{" "}
                extraction
              </p>
              <dl className="mt-3 space-y-2">
                {Object.entries(source.evidence).map(([key, value]) => (
                  <div key={key} className="text-xs leading-relaxed">
                    <dt className="font-semibold text-ink-soft">
                      {label(key)}
                    </dt>
                    <dd className="break-words">“{value}”</dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ul>
        <details className="mt-4 rounded-xl border p-3 text-xs">
          <summary className="cursor-pointer font-medium">
            Confidence factors
          </summary>
          <dl className="mt-3 space-y-2">
            {Object.entries(detail.confidence_factors).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3">
                <dt>{label(key)}</dt>
                <dd>{value === null ? "Unavailable" : value}</dd>
              </div>
            ))}
          </dl>
        </details>
      </section>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const minor = inputPaise(amount);
          if (!minor || !merchant.trim()) {
            setValidation(
              "Use a merchant name and a positive amount with at most two decimal places.",
            );
            return;
          }
          setValidation("");
          const changed: Correction = {};
          if (category !== tx.category) changed.category = category;
          if (merchant.trim() !== tx.merchant)
            changed.merchant = merchant.trim();
          if (minor !== tx.amount_minor) changed.amount_minor = minor;
          if (!Object.keys(changed).length) {
            setValidation("No changes to save.");
            return;
          }
          mutate("correct", changed);
        }}
        className="space-y-3 border-t pt-5"
      >
        <h3 className="font-semibold">Make a correction</h3>
        <label className="block text-xs">
          Category
          <select
            value={category}
            onChange={(event) => {
              const parsed = categorySchema.safeParse(event.target.value);
              if (parsed.success) setCategory(parsed.data);
            }}
            className="mt-2 block h-11 w-full rounded-xl border px-3"
          >
            {categories.map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs">
          Merchant
          <input
            value={merchant}
            onChange={(event) => setMerchant(event.target.value)}
            maxLength={160}
            className="mt-2 block h-11 w-full rounded-xl border px-3"
          />
        </label>
        <label className="block text-xs">
          Amount (₹)
          <input
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            className="mt-2 block h-11 w-full rounded-xl border px-3"
          />
        </label>
        {validation && (
          <p role="alert" className="text-xs text-destructive">
            {validation}
          </p>
        )}
        <Button type="submit" disabled={busy}>
          Save correction
        </Button>
      </form>
      {tx.status === "needs_review" && (
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => mutate("confirm")}>
            Confirm record
          </Button>
          <Button
            variant="destructive"
            disabled={busy}
            onClick={() => mutate("reject")}
          >
            Reject record
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => mutate("keep-separate")}
          >
            Keep separate
          </Button>
        </div>
      )}
      {tx.status === "needs_review" && (
        <fieldset className="space-y-3 rounded-2xl border p-4">
          <legend className="px-2 text-sm font-medium">
            Only if this is the same payment
          </legend>
          <label className="block text-xs">
            Keep this existing record
            <select
              value={keepId}
              onChange={(event) => setKeepId(event.target.value)}
              className="mt-2 block h-11 w-full rounded-xl border px-3"
            >
              <option value="">Choose a record to keep</option>
              {rows
                .filter(
                  (row) =>
                    row.id !== tx.id &&
                    row.status !== "merged" &&
                    row.status !== "rejected",
                )
                .map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.merchant} · {formatMoney(row.amount_minor)}
                  </option>
                ))}
            </select>
          </label>
          <Button
            variant="outline"
            disabled={busy || !keepId}
            onClick={() => mutate("merge", undefined, keepId)}
          >
            Merge into selected record
          </Button>
        </fieldset>
      )}
      <section className="border-t pt-5">
        <h3 className="font-semibold">Revision history</h3>
        {!detail.revisions.length ? (
          <p className="mt-3 text-xs text-ink-soft">No corrections yet.</p>
        ) : (
          <ol className="mt-3 space-y-3">
            {detail.revisions.map((revision) => (
              <li
                key={revision.id}
                className="break-words text-xs leading-relaxed"
              >
                <strong>{label(revision.field)}</strong> · {revision.changed_by}
                <p>
                  {revisionValue(revision.field, revision.old_value)} →{" "}
                  {revisionValue(revision.field, revision.new_value)}
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function revisionValue(field: string, value: unknown): string {
  if (field === "amount_minor" && typeof value === "number")
    return formatMoney(value);
  if (typeof value === "string") return label(value);
  if (typeof value === "number") return String(value);
  if (Array.isArray(value))
    return (
      value
        .filter((item) => typeof item === "string")
        .map((item) => label(item))
        .join(", ") || "None"
    );
  if (value === null) return "Not set";
  return "Evidence factors updated";
}
