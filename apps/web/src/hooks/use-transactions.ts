"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getTransactions,
  getTransaction,
  correctTransaction,
  reviewTransaction,
  type Correction,
  type TransactionDetail,
} from "@/lib/api/transactions";
import type { Transaction } from "@/lib/api/money";

export function useTransactions(reviewOnly = false) {
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [detail, setDetail] = useState<TransactionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState(reviewOnly ? "needs_review" : "");
  const detailControl = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  const refresh = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    const control = new AbortController();
    const params = new URLSearchParams({ limit: "200" });
    if (query.trim()) params.set("q", query.trim());
    if (status) params.set("status", status);
    void getTransactions(params.toString(), control.signal).then(
      (result) => {
        if (!control.signal.aborted) {
          setRows(result);
          setError(null);
        }
      },
      () => {
        if (!control.signal.aborted)
          setError(
            "Could not load transactions. Check your connection and try again.",
          );
      },
    );
    return () => control.abort();
  }, [query, status, version]);
  useEffect(() => () => detailControl.current?.abort(), []);
  async function inspect(id: string) {
    detailControl.current?.abort();
    const control = new AbortController();
    detailControl.current = control;
    setDetail(null);
    setDetailLoading(true);
    setError(null);
    try {
      const result = await getTransaction(id, control.signal);
      if (!control.signal.aborted) setDetail(result);
    } catch {
      if (!control.signal.aborted)
        setError("Could not load this transaction’s evidence.");
    } finally {
      if (!control.signal.aborted) setDetailLoading(false);
    }
  }
  function close() {
    detailControl.current?.abort();
    setDetail(null);
    setDetailLoading(false);
  }
  async function mutate(
    action: "correct" | "confirm" | "reject" | "merge" | "keep-separate",
    correction?: Correction,
    keepId?: string,
  ) {
    if (!detail || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const result =
        action === "correct"
          ? await correctTransaction(detail.transaction.id, correction ?? {})
          : await reviewTransaction(detail.transaction.id, action, keepId);
      setDetail(result);
      refresh();
    } catch {
      setError(
        "This change could not be saved. Check the values and connection, then try again.",
      );
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return {
    rows,
    detail,
    error,
    detailLoading,
    busy,
    query,
    setQuery,
    status,
    setStatus,
    refresh,
    inspect,
    close,
    mutate,
  };
}
