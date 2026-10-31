"use client";

import { Search, SlidersHorizontal, X } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { categories, kinds, statuses } from "@/lib/api/money";
import { monthLabel, recentMonths } from "@/lib/dates";
import { categoryLabels, kindLabels, statusLabels } from "@/lib/labels";
import { shortcutsEnabled, typingTarget } from "@/lib/shortcuts";
import { cn } from "@/lib/utils";

const FILTER_KEYS = ["q", "status", "category", "kind", "source", "scope", "year", "month", "dataset"];
// What the phone filter button counts: everything except the search text (shown in the field).
const PANEL_FILTERS = [["status"], ["category"], ["kind"], ["source"], ["scope", "year", "month"]];

/** Recent calendar months (IST), newest first, for the period selector. */
const selectClass = "field field-select mt-1.5 block h-11 w-full rounded-lg pl-3 text-sm";

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
  // Phones show the reference's search + filter button; wider screens keep every filter open.
  const [open, setOpen] = useState(false);
  const applied = PANEL_FILTERS.filter((keys) => keys.some((key) => params.has(key))).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <label htmlFor={`${ids}-q`} className="sr-only">
            Search merchant or payer
          </label>
          <Search className="pointer-events-none absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-ink-soft" aria-hidden="true" />
          <input
            ref={searchRef}
            id={`${ids}-q`}
            type="search"
            value={draft}
            maxLength={160}
            placeholder="Search merchant or payer"
            aria-describedby={`${ids}-q-hint`}
            onChange={(event) => setDraft(event.target.value)}
            className="field block h-12 w-full rounded-lg pr-4 pl-11 text-sm"
          />
          <p id={`${ids}-q-hint`} className="sr-only">
            Results update as you type. Press slash to jump here.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-lg"
          className="field relative size-12 rounded-lg"
          aria-expanded={open}
          aria-controls={`${ids}-panel`}
          aria-label={applied ? `Filters, ${applied} on` : "Filters"}
          onClick={() => setOpen((value) => !value)}
        >
          <SlidersHorizontal className="size-[18px]" aria-hidden="true" />
          {applied > 0 && (
            <span aria-hidden="true" className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full bg-ink text-[11px] font-semibold text-white">
              {applied}
            </span>
          )}
        </Button>
      </div>
      <div id={`${ids}-panel`} className={cn("surface grid gap-3 rounded-3xl p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-5", !open && "hidden")}>
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
              <option value="manual_entry">Added by you</option>
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
              <option value="manual_entry">Added by you</option>
            </select>
          </div>
        )}
      </div>
      {active && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setDraft("");
            update(Object.fromEntries([...FILTER_KEYS, "offset"].map((key) => [key, null])));
          }}
        >
          <X aria-hidden="true" /> Clear filters
        </Button>
      )}
    </div>
  );
}
