"use client";

import { useState, type FormEvent } from "react";
import {
  DIARY_CATEGORIES,
  diaryCsv,
  diaryTotals,
  parseRupees,
  type DiaryCategory,
  type DiaryEntry,
  type PaymentMethod,
} from "@/lib/cash-upi-diary";

const field = "mt-1.5 w-full rounded-xl border border-ink/20 bg-white px-3 py-2.5 text-base text-ink focus:outline-2 focus:outline-offset-2 focus:outline-ink";
const money = (minor: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(minor / 100);

function localDate() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}

export function CashUpiDiary() {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("UPI");
  const [category, setCategory] = useState<DiaryCategory>("Food and groceries");
  const [error, setError] = useState("");
  const [nextId, setNextId] = useState(1);

  function addEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amountMinor = parseRupees(amount);
    if (!amountMinor) {
      setError("Enter an amount greater than zero, using up to two decimal places. Do not use commas.");
      return;
    }
    if (entries.length >= 500) {
      setError("This diary holds up to 500 entries. Download your CSV before starting a new one.");
      return;
    }
    const trimmed = description.trim();
    if (!trimmed) {
      setError("Add a short description.");
      return;
    }
    setEntries((current) => [...current, { id: nextId, date: date || localDate(), description: trimmed, method, category, amountMinor }]);
    setNextId((current) => current + 1);
    setDescription("");
    setAmount("");
    setError("");
  }

  function download() {
    const blob = new Blob([diaryCsv(entries)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "cash-upi-expense-diary.csv";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const totals = diaryTotals(entries);
  return (
    <section aria-labelledby="diary-heading" className="surface rounded-3xl p-5 sm:p-8">
      <h2 id="diary-heading" className="text-2xl font-semibold tracking-tight">Your diary</h2>
      <p className="mt-2 text-sm leading-relaxed text-ink-soft">
        Entries stay in this browser tab and are not sent to FinBoy. Reloading the page clears
        them. Download a CSV if you want to keep a copy on your device.
      </p>
      <form onSubmit={addEntry} className="mt-6 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-semibold" htmlFor="diary-date">
          Date (leave blank for today)
          <input id="diary-date" className={field} type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        <label className="text-sm font-semibold" htmlFor="diary-description">
          What did you buy?
          <input id="diary-description" className={field} required maxLength={100} placeholder="For example, tea" value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label className="text-sm font-semibold" htmlFor="diary-amount">
          Amount in rupees
          <input id="diary-amount" className={field} type="text" inputMode="decimal" required maxLength={12} placeholder="For example, 20.50" value={amount} onChange={(event) => setAmount(event.target.value)} aria-describedby={error ? "diary-error" : undefined} />
        </label>
        <label className="text-sm font-semibold" htmlFor="diary-method">
          Paid with
          <select id="diary-method" className={field} value={method} onChange={(event) => setMethod(event.target.value === "Cash" ? "Cash" : "UPI")}>
            <option>UPI</option><option>Cash</option>
          </select>
        </label>
        <label className="text-sm font-semibold" htmlFor="diary-category">
          Category
          <select id="diary-category" className={field} value={category} onChange={(event) => {
            const value = DIARY_CATEGORIES.find((item) => item === event.target.value);
            if (value) setCategory(value);
          }}>
            {DIARY_CATEGORIES.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <div className="flex items-end">
          <button type="submit" className="min-h-11 rounded-full bg-ink px-6 py-2.5 text-sm font-semibold text-white">Add expense</button>
        </div>
        {error && <p id="diary-error" role="alert" className="text-sm font-semibold text-red-800 sm:col-span-2">{error}</p>}
      </form>
      <div aria-live="polite" className="mt-8 grid grid-cols-1 gap-3 min-[390px]:grid-cols-3">
        {[{ label: "Cash", value: totals.Cash }, { label: "UPI", value: totals.UPI }, { label: "Total", value: totals.total }].map((item) => (
          <div key={item.label} className="rounded-2xl bg-white/70 p-4">
            <p className="text-sm text-ink-soft">{item.label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums">{money(item.value)}</p>
          </div>
        ))}
      </div>
      <div className="mt-7 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">Entries ({entries.length})</h3>
        <button type="button" onClick={download} disabled={!entries.length} className="min-h-11 rounded-full border border-ink px-5 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40">Download CSV</button>
      </div>
      {entries.length === 0 ? <p className="mt-3 text-sm text-ink-soft">No expenses added yet.</p> : (
        <ul className="mt-3 divide-y divide-ink/10">
          {entries.map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-start justify-between gap-3 py-4">
              <div className="min-w-0 break-words">
                <p className="font-semibold">{entry.description}</p>
                <p className="text-sm text-ink-soft">{entry.date} · {entry.method} · {entry.category}</p>
              </div>
              <div className="flex items-center gap-4">
                <span className="font-semibold tabular-nums">{money(entry.amountMinor)}</span>
                <button type="button" className="min-h-11 text-sm font-semibold underline underline-offset-4" aria-label={`Remove ${entry.description}`} onClick={() => setEntries((current) => current.filter((item) => item.id !== entry.id))}>Remove</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
