"use client";

import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useResource } from "@/hooks/use-resource";
import { categorySchema, kindSchema, statusSchema, type Period } from "@/lib/api/money";
import {
  getTransactionPage,
  recordQueryString,
  type RecordQuery,
} from "@/lib/api/transactions";

export const PAGE_SIZE = 50;

function boundedInt(value: string | null, min: number, max: number): number | null {
  if (!value || !/^\d{1,7}$/.test(value)) return null;
  const parsed = Number(value);
  return parsed >= min && parsed <= max ? parsed : null;
}

/** Reads list state from the URL; unknown or unsafe values are ignored rather than sent. */
export function readRecordQuery(params: URLSearchParams, view: "transactions" | "review"): RecordQuery {
  const year = boundedInt(params.get("year"), 2000, 2100);
  const month = boundedInt(params.get("month"), 1, 12);
  const period: Period = year && month ? { year, month } : null;
  const source = params.get("source");
  const q = params.get("q")?.trim().slice(0, 160);
  const offset = boundedInt(params.get("offset"), 0, 1_000_000) ?? 0;
  return {
    scope: view === "review" ? "unresolved" : params.get("scope") === "all" ? "all" : "month",
    period,
    status: view === "transactions" ? statusSchema.safeParse(params.get("status")).data : undefined,
    category: categorySchema.safeParse(params.get("category")).data,
    kind: kindSchema.safeParse(params.get("kind")).data,
    source:
      source === "gmail" ||
      source === "eml_upload" ||
      source === "whatsapp_image" ||
      source === "whatsapp_voice" ||
      source === "manual_entry"
        ? source
        : undefined,
    q: q || undefined,
    dataset: view === "transactions" && params.get("dataset") === "quarantined" ? "quarantined" : undefined,
    limit: PAGE_SIZE,
    offset: offset - (offset % PAGE_SIZE),
  };
}

/**
 * The visible page of records for the URL's filters. Moving between pages pins the data
 * version of the page the person was looking at, so a change in between is reported (409)
 * instead of silently skipping or repeating records.
 */
export function useRecordList(view: "transactions" | "review") {
  const params = useSearchParams();
  const query = useMemo(() => readRecordQuery(new URLSearchParams(params.toString()), view), [params, view]);
  const [pinned, setPinned] = useState<{ key: string; version: string } | null>(null);
  const base = recordQueryString({ ...query, offset: 0 });
  const version = pinned && pinned.key === base && query.offset > 0 ? pinned.version : undefined;
  const list = useResource(`records:${recordQueryString(query)}:${version ?? ""}`, (signal) =>
    getTransactionPage({ ...query, ...(version ? { data_version: version } : {}) }, signal),
  );
  return {
    query,
    list,
    filterKey: base,
    /** Call before moving to another page of the same filter. */
    pinVersion: (dataVersion: string) => setPinned({ key: base, version: dataVersion }),
    unpin: () => setPinned(null),
  };
}
