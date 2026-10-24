"use client";

import { useCallback, useRef, useState } from "react";
import { isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";

/** One user-triggered mutation at a time, with its own pending name and task-specific failure. */
export function useAction() {
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [lastError, setLastError] = useState<unknown>(null);
  const flight = useRef(false);
  const run = useCallback(
    async <T>(name: string, failureTitle: string, task: () => Promise<T>): Promise<T | undefined> => {
      if (flight.current) return undefined;
      flight.current = true;
      setBusy(name);
      setProblem(null);
      setLastError(null);
      try {
        return await task();
      } catch (error) {
        if (!isAbort(error)) {
          setProblem(describeProblem(error, failureTitle));
          setLastError(error);
        }
        return undefined;
      } finally {
        flight.current = false;
        setBusy(null);
      }
    },
    [],
  );
  const clear = useCallback(() => {
    setProblem(null);
    setLastError(null);
  }, []);
  return { busy, problem, lastError, run, clear };
}
