"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getCommitments,
  getSummary,
  simulate,
  type MoneySummary,
  type Commitment,
  type Simulation,
} from "@/lib/api/money";

export function useMoney() {
  const [data, setData] = useState<{
    summary: MoneySummary;
    commitments: Commitment[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const refresh = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    const control = new AbortController();
    void Promise.all([
      getSummary(control.signal),
      getCommitments(control.signal),
    ]).then(
      ([summary, commitments]) => {
        if (!control.signal.aborted) {
          setData({ summary, commitments });
          setError(null);
        }
      },
      () => {
        if (!control.signal.aborted)
          setError(
            "Could not load your records. Check the API connection and try again.",
          );
      },
    );
    return () => control.abort();
  }, [version]);
  async function runSimulation(amount: number) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      setSimulation(await simulate(amount));
    } catch {
      setError(
        "Simulation is unavailable. Please check your connection and try again.",
      );
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return { data, error, refresh, simulation, busy, runSimulation };
}
