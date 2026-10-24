"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, isAbort } from "@/lib/api/http";
import { getImportRun, isActive, type ImportRun } from "@/lib/api/imports";
import { describeProblem, type Problem } from "@/lib/messages";
import { onSessionEvent } from "@/lib/session-events";

const STOP_KINDS = new Set(["not_found", "session", "forbidden", "invalid_response", "configuration"]);

/**
 * Follows one import. Active runs are polled; a transient failure keeps the last status and
 * retries with bounded backoff (and immediately when the device reconnects), so a dropped
 * request never strands the page.
 */
export function useImportRun(runId: string) {
  const [run, setRun] = useState<ImportRun | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [retrying, setRetrying] = useState(false);
  const [version, setVersion] = useState(0);
  const pollNow = useRef<() => void>(() => undefined);
  const refresh = useCallback(() => setVersion((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let inFlight = false;
    async function poll() {
      if (inFlight || controller.signal.aborted) return;
      inFlight = true;
      clearTimeout(timer);
      try {
        const result = await getImportRun(runId, controller.signal);
        if (controller.signal.aborted) return;
        attempt = 0;
        setRun(result);
        setProblem(null);
        setError(null);
        setRetrying(false);
        if (isActive(result)) timer = setTimeout(poll, 1_500);
      } catch (reason) {
        if (controller.signal.aborted || isAbort(reason)) return;
        attempt += 1;
        setError(reason);
        setProblem(describeProblem(reason, "Couldn't refresh this import"));
        const stop = reason instanceof ApiError && STOP_KINDS.has(reason.kind);
        setRetrying(!stop);
        if (!stop) timer = setTimeout(poll, Math.min(30_000, 1_000 * 2 ** attempt));
      } finally {
        inFlight = false;
      }
    }
    pollNow.current = () => void poll();
    void poll();
    const resume = () => void poll();
    window.addEventListener("online", resume);
    const stopSession = onSessionEvent("restored", resume);
    return () => {
      controller.abort();
      clearTimeout(timer);
      window.removeEventListener("online", resume);
      stopSession();
    };
  }, [runId, version]);

  return { run, problem, error, retrying, refresh, replace: setRun };
}
