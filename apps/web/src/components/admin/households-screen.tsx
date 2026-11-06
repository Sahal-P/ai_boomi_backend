"use client";

import { Mail, MessageCircle, Search, SlidersHorizontal, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Dialog } from "radix-ui";
import { useEffect, useId, useState } from "react";
import { count, day, Pager, RefreshButton } from "@/components/admin/admin-bits";
import { HouseholdDetailView, StatusBadge } from "@/components/admin/household-detail";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { EmptyState, LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { NoMatchArt } from "@/components/illustrations/scenes";
import { Button } from "@/components/ui/button";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useResource } from "@/hooks/use-resource";
import { kindLabels, planLabels, statusLabels } from "@/lib/admin-labels";
import {
  KINDS,
  listHouseholds,
  PLAN_STATES,
  STATUSES,
  type HouseholdFilters,
  type HouseholdRow,
} from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const FILTERS = ["kind", "status", "plan", "active"] as const;
const selectClass = "field field-select mt-1.5 block h-11 w-full rounded-lg pl-3 text-sm";

function oneOf<T extends string>(values: readonly T[], value: string | null): T | null {
  return values.find((item) => item === value) ?? null;
}

function readFilters(params: URLSearchParams): Required<HouseholdFilters> {
  const offset = Number(params.get("offset") ?? 0);
  const active = params.get("active");
  return {
    q: (params.get("q") ?? "").slice(0, 64),
    kind: oneOf(KINDS, params.get("kind")),
    status: oneOf(STATUSES, params.get("status")),
    plan: oneOf(PLAN_STATES, params.get("plan")),
    active: active === "7" ? 7 : active === "30" ? 30 : null,
    offset: Number.isInteger(offset) && offset > 0 ? offset : 0,
  };
}

function Filters({ filters }: { filters: Required<HouseholdFilters> }) {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const ids = useId();
  const urlQuery = filters.q ?? "";
  const [draft, setDraft] = useState(urlQuery);
  const [seen, setSeen] = useState(urlQuery);
  const [open, setOpen] = useState(false);
  if (seen !== urlQuery) {
    setSeen(urlQuery);
    setDraft(urlQuery);
  }
  useEffect(() => {
    if (draft.trim() === urlQuery.trim()) return;
    const timer = setTimeout(() => update({ q: draft.trim().slice(0, 64) || null, offset: null, selected: null }), 350);
    return () => clearTimeout(timer);
  }, [draft, urlQuery, update]);
  const applied = FILTERS.filter((key) => params.has(key)).length;
  const set = (key: (typeof FILTERS)[number], value: string) => update({ [key]: value || null, offset: null, selected: null });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <label htmlFor={`${ids}-q`} className="sr-only">
            Household ID or phone number
          </label>
          <Search className="pointer-events-none absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-ink-soft" aria-hidden="true" />
          <input
            id={`${ids}-q`}
            type="search"
            value={draft}
            maxLength={64}
            autoComplete="off"
            spellCheck={false}
            placeholder="Household ID or phone number"
            aria-describedby={`${ids}-q-hint`}
            onChange={(event) => setDraft(event.target.value)}
            className="field block h-12 w-full rounded-lg pr-4 pl-11 text-sm"
          />
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
      <p id={`${ids}-q-hint`} className="text-xs text-ink-soft">
        A phone number must be exact, with or without +91. Numbers are matched by their hash and never listed.
      </p>
      <div id={`${ids}-panel`} className={cn("surface grid gap-3 rounded-3xl p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4", !open && "hidden")}>
        <div>
          <label htmlFor={`${ids}-kind`} className="text-xs font-semibold">
            Kind
          </label>
          <select id={`${ids}-kind`} className={selectClass} value={filters.kind ?? ""} onChange={(event) => set("kind", event.target.value)}>
            <option value="">All kinds</option>
            {KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kindLabels[kind]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${ids}-status`} className="text-xs font-semibold">
            Status
          </label>
          <select id={`${ids}-status`} className={selectClass} value={filters.status ?? ""} onChange={(event) => set("status", event.target.value)}>
            <option value="">Any status</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${ids}-plan`} className="text-xs font-semibold">
            Plan
          </label>
          <select id={`${ids}-plan`} className={selectClass} value={filters.plan ?? ""} onChange={(event) => set("plan", event.target.value)}>
            <option value="">Any plan</option>
            {PLAN_STATES.map((state) => (
              <option key={state} value={state}>
                {planLabels[state]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${ids}-active`} className="text-xs font-semibold">
            Last active
          </label>
          <select id={`${ids}-active`} className={selectClass} value={filters.active ? String(filters.active) : ""} onChange={(event) => set("active", event.target.value)}>
            <option value="">Any time</option>
            <option value="7">In the last 7 days</option>
            <option value="30">In the last 30 days</option>
          </select>
        </div>
      </div>
    </div>
  );
}

function Row({ row, href, selected }: { row: HouseholdRow; href: string; selected: boolean }) {
  return (
    <Link
      href={href}
      replace
      scroll={false}
      data-household-id={row.id}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "surface grid w-full grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 rounded-lg px-3.5 py-3 text-left transition-colors hover:bg-white/70 sm:px-4",
        selected && "bg-white/90 ring-[1.5px] ring-ink hover:bg-white/90",
      )}
    >
      <span className="min-w-0">
        <span className="block font-mono text-sm font-semibold">{row.short_id}</span>
        <span className="mt-0.5 block text-xs text-ink-soft">
          {kindLabels[row.kind]} · {planLabels[row.plan]} · joined {day(row.joined_at)}
        </span>
        <span className="mt-0.5 block text-xs text-ink-soft">
          {row.last_active_at ? `Last active ${day(row.last_active_at)}` : "Not active yet"}
        </span>
      </span>
      <span className="flex flex-col items-end gap-1.5">
        {row.status !== "active" && <StatusBadge status={row.status} />}
        <span className="flex gap-1 text-ink-soft">
          {row.whatsapp && (
            <span title="WhatsApp linked">
              <MessageCircle className="size-4" aria-hidden="true" />
              <span className="sr-only">WhatsApp linked</span>
            </span>
          )}
          {row.google && (
            <span title="Google linked">
              <Mail className="size-4" aria-hidden="true" />
              <span className="sr-only">Google linked</span>
            </span>
          )}
        </span>
      </span>
    </Link>
  );
}

/** What the last action did, read out politely. */
function Announcement({ text, onDismiss }: { text: string; onDismiss: () => void }) {
  return (
    <div role="status" aria-live="polite">
      {text && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-ink px-4 py-2.5 text-sm text-white">
          <span>{text}</span>
          <button
            type="button"
            className="ml-auto min-h-11 px-2 text-xs font-semibold text-white/85 underline underline-offset-4"
            onClick={onDismiss}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

/** Find a household by ID or exact number, filter the list, and act on one beside it. */
export function HouseholdsScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const wide = useMediaQuery("(min-width: 64rem)");
  const filters = readFilters(params);
  // Refresh loads the open household again too; the list keeps showing while it reloads.
  const [version, setVersion] = useState(0);
  const [announcement, setAnnouncement] = useState("");
  const list = useResource(`admin-households:${JSON.stringify(filters)}`, (signal) => listHouseholds(filters, signal));
  const page = list.stale ? null : list.data;
  const selectedParam = params.get("selected");
  const selected = selectedParam && UUID.test(selectedParam) ? selectedParam.toLowerCase() : null;
  const filtered = Boolean(filters.q || filters.kind || filters.status || filters.plan || filters.active);
  // A household opened afresh starts without the last one's message (an erase keeps its own).
  const [openFor, setOpenFor] = useState(selected);
  if (openFor !== selected) {
    setOpenFor(selected);
    if (selected) setAnnouncement("");
  }

  function hrefFor(id: string) {
    const next = new URLSearchParams(params.toString());
    next.set("selected", id);
    return `/admin/households?${next.toString()}`;
  }

  const detail = selected && (
    <HouseholdDetailView
      key={selected}
      householdId={selected}
      version={version}
      focusOnLoad={!wide}
      onChanged={list.reload}
      onErased={() => {
        update({ selected: null });
        list.reload();
      }}
      announce={setAnnouncement}
    />
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Households"
        description="Activity, plans and dates. Records, messages, names and numbers are never shown."
        actions={
          <RefreshButton
            resource={{
              ...list,
              reload: () => {
                list.reload();
                setVersion((value) => value + 1);
              },
            }}
          />
        }
      />
      <Filters filters={filters} />
      {/* On phones the household is a modal, which hides the page from screen readers: the
          announcement moves inside it while it is open. */}
      {(wide || !selected) && <Announcement text={announcement} onDismiss={() => setAnnouncement("")} />}

      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">
          {page ? `${count(page.total)} ${page.total === 1 ? "household" : "households"}` : "Households"}
          {page && filtered && <span className="font-normal text-ink-soft"> match</span>}
        </h2>
      </div>
      <RefreshingLabel active={list.status === "refreshing"}>Updating the list…</RefreshingLabel>
      {list.status === "loading" && <LoadingPanel label="Loading households…" />}
      {list.error !== null && (
        <ProblemNotice
          problem={describeProblem(list.error, list.data ? "Couldn't refresh — showing the last loaded list" : "Households couldn't be loaded")}
          onRetry={list.reload}
        />
      )}
      {page && page.items.length === 0 && (
        <EmptyState
          illustration={<NoMatchArt />}
          title={filters.q ? "No household matches that search" : "No households match these filters"}
          actions={
            filtered ? (
              <Button variant="outline" onClick={() => update({ q: null, kind: null, status: null, plan: null, active: null, offset: null, selected: null })}>
                Clear search and filters
              </Button>
            ) : undefined
          }
        >
          {filters.q
            ? "Search takes a household ID (or its first characters) or an exact phone number."
            : "Try another kind, status or plan."}
        </EmptyState>
      )}

      {page && page.items.length > 0 && (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <div className={list.status === "refreshing" ? "opacity-70" : undefined}>
            <ul aria-label="Households" className="space-y-2">
              {page.items.map((row) => (
                <li key={row.id}>
                  <Row row={row} href={hrefFor(row.id)} selected={row.id === selected} />
                </li>
              ))}
            </ul>
            <Pager
              label="Household pages"
              offset={page.offset}
              shown={page.items.length}
              total={page.total}
              nextOffset={page.next_offset}
              onPage={(offset) => update({ offset: offset ? String(offset) : null, selected: null })}
            />
          </div>
          {wide && (
            <section aria-label="Household" className="surface rounded-3xl p-5 sm:p-6 lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto">
              {detail || <p className="text-sm text-ink-soft">Choose a household to see its activity, plan and what you can do.</p>}
            </section>
          )}
        </div>
      )}

      {!wide && (
        <Dialog.Root open={selected !== null} onOpenChange={(open) => !open && update({ selected: null })}>
          <Dialog.Portal>
            {/* Unblurred: a confirmation's own overlay blurs above it, within the 3-layer budget. */}
            <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/25" />
            <Dialog.Content
              aria-describedby={undefined}
              onCloseAutoFocus={(event) => {
                event.preventDefault();
                const row = selectedParam ? document.querySelector<HTMLElement>(`[data-household-id="${CSS.escape(selectedParam)}"]`) : null;
                row?.focus();
              }}
              // Opaque (the float panel's reduced-transparency colour): its overlay isn't blurred, so a
              // translucent sheet would let the page behind show through.
              className="fixed inset-x-2 bottom-[max(0.5rem,env(safe-area-inset-bottom))] z-50 max-h-[94dvh] overflow-y-auto rounded-[32px] lg-thick bg-[#fcfcfd] p-5 pb-8 sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:max-h-[90dvh] sm:w-[calc(100%-2rem)] sm:max-w-2xl sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[28px] sm:p-8"
            >
              <Dialog.Title className="sr-only">Household details</Dialog.Title>
              <Announcement text={announcement} onDismiss={() => setAnnouncement("")} />
              <div className="mb-2 flex justify-end">
                <Dialog.Close asChild>
                  <Button variant="ghost" size="icon" aria-label="Close household">
                    <X className="size-5" aria-hidden="true" />
                  </Button>
                </Dialog.Close>
              </div>
              {detail}
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      )}
    </div>
  );
}
