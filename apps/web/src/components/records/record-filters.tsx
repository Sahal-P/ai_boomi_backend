"use client";

import { Search, X } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { categories, kinds, statuses } from "@/lib/api/money";
import { istDate, monthLabel } from "@/lib/dates";
import { categoryLabels, kindLabels, statusLabels } from "@/lib/labels";
import { shortcutsEnabled, typingTarget } from "@/lib/shortcuts";

const FILTER_KEYS = ["q", "status", "category", "kind", "source", "scope", "year", "month", "dataset"];

/** Recent calendar months (IST), newest first, for the period selector. */
function recentMonths(count: number): { year: number; month: number }[] {
  const [year = 2026, month = 1] = istDate(new Date()).split("-").map(Number);
  return Array.from({ length: count }, (_, index) => {
    const offset = month - 1 - index;
    return { year: year + Math.floor(offset / 12), month: (((offset % 12) + 12) % 12) + 1 };
  });
}

const selectClass = "mt-1.5 block h-11 w-full rounded-xl border border-input bg-white px-3 text-sm";

/** URL-backed filters; search is debounced so typing doesn't fire a request per key. */
export function RecordFilters({ view }: { view: "transactions" | "review" }) {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const ids = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const urlQuery = params.get("q") ?? "";
  const [draft, setDraft] = useState(urlQuery);
  const [seen, setSeen] = useState(urlQuery);
  if (seen !== urlQuery) {
    // Back/Forward or "Clear filters" changed the URL: show what the list is filtered by.
    setSeen(urlQuery);
    setDraft(urlQuery);
  }

  useEffect(() => {
    if (draft.trim() === urlQuery.trim()) return;
    const timer = setTimeout(() => update({ q: draft.trim().slice(0, 160) || null, offset: null }), 350);
    return () => clearTimeout(timer);
  }, [draft, urlQuery, update]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      if (!shortcutsEnabled() || typingTarget(event.target)) return;
      event.preventDefault();
      searchRef.current?.focus();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const year = params.get("year");
  const month = params.get("month");
  const scope = params.get("scope") === "all" ? "all" : "month";
  const periodValue = year && month ? `${year}-${month}` : view === "review" ? "" : scope === "all" ? "all" : "current";
  const active = FILTER_KEYS.some((key) => params.has(key));
  const set = (updates: Record<string, string | null>) => update({ ...updates, offset: null });

  return (
    <div className="surface rounded-3xl p-4 sm:p-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <label htmlFor={`${ids}-q`} className="text-xs font-semibold">
            Search merchant or payer
          </label>
          <div className="relative mt-1.5">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-soft" aria-hidden="true" />
            <input
              ref={searchRef}
              id={`${ids}-q`}
              type="search"
              value={draft}
              maxLength={160}
              placeholder="For example, Amazon"
              aria-describedby={`${ids}-q-hint`}
              onChange={(event) => setDraft(event.target.value)}
              className="block h-11 w-full rounded-xl border border-input bg-white pr-3 pl-9 text-sm"
            />
          </div>
          <p id={`${ids}-q-hint`} className="sr-only">
            Results update as you type. Press slash to jump here.
          </p>
        </div>
        <div>
          <label htmlFor={`${ids}-period`} className="text-xs font-semibold">
            Period
          </label>
          <select
            id={`${ids}-period`}
            value={periodValue}
            className={selectClass}
            onChange={(event) => {
              const value = event.target.value;
              if (value === "" || value === "current") set({ scope: null, year: null, month: null });
              else if (value === "all") set({ scope: "all", year: null, month: null });
              else {
                const [y, m] = value.split("-");
                set({ scope: null, year: y ?? null, month: m ?? null });
              }
            }}
          >
            {view === "review" ? (
              <option value="">All unresolved (any date)</option>
            ) : (
              <>
                <option value="current">This month</option>
                <option value="all">All time</option>
              </>
            )}
            {recentMonths(18).map((item) => (
              <option key={`${item.year}-${item.month}`} value={`${item.year}-${item.month}`}>
                {monthLabel(item.year, item.month)}
              </option>
            ))}
          </select>
        </div>
        {view === "transactions" ? (
          <div>
            <label htmlFor={`${ids}-status`} className="text-xs font-semibold">
              Status
            </label>
            <select
              id={`${ids}-status`}
              value={params.get("status") ?? ""}
              className={selectClass}
              onChange={(event) => set({ status: event.target.value || null })}
            >
              <option value="">Any status</option>
              {statuses.map((value) => (
                <option key={value} value={value}>
                  {statusLabels[value]}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div>
            <label htmlFor={`${ids}-source`} className="text-xs font-semibold">
              Source
            </label>
            <select
              id={`${ids}-source`}
              value={params.get("source") ?? ""}
              className={selectClass}
              onChange={(event) => set({ source: event.target.value || null })}
            >
              <option value="">Any source</option>
              <option value="gmail">Gmail</option>
              <option value="eml_upload">Uploaded emails</option>
              <option value="whatsapp_image">WhatsApp screenshots</option>
              <option value="whatsapp_voice">WhatsApp voice notes</option>
            </select>
          </div>
        )}
        <div>
          <label htmlFor={`${ids}-category`} className="text-xs font-semibold">
            Category
          </label>
          <select
            id={`${ids}-category`}
            value={params.get("category") ?? ""}
            className={selectClass}
            onChange={(event) => set({ category: event.target.value || null })}
          >
            <option value="">Any category</option>
            {categories.map((value) => (
              <option key={value} value={value}>
                {categoryLabels[value]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${ids}-kind`} className="text-xs font-semibold">
            Type
          </label>
          <select
            id={`${ids}-kind`}
            value={params.get("kind") ?? ""}
            className={selectClass}
            onChange={(event) => set({ kind: event.target.value || null })}
          >
            <option value="">Any type</option>
            {kinds.map((value) => (
              <option key={value} value={value}>
                {kindLabels[value]}
              </option>
            ))}
          </select>
        </div>
        {view === "transactions" && (
          <div>
            <label htmlFor={`${ids}-source`} className="text-xs font-semibold">
              Source
            </label>
            <select
              id={`${ids}-source`}
              value={params.get("source") ?? ""}
              className={selectClass}
              onChange={(event) => set({ source: event.target.value || null })}
            >
              <option value="">Any source</option>
              <option value="gmail">Gmail</option>
              <option value="eml_upload">Uploaded emails</option>
              <option value="whatsapp_image">WhatsApp screenshots</option>
              <option value="whatsapp_voice">WhatsApp voice notes</option>
            </select>
          </div>
        )}
        {active && (
          <div className="flex items-end">
            <Button
              variant="ghost"
              className="w-full sm:w-auto"
              onClick={() => {
                setDraft("");
                update(Object.fromEntries([...FILTER_KEYS, "offset"].map((key) => [key, null])));
              }}
            >
              <X aria-hidden="true" /> Clear filters
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
