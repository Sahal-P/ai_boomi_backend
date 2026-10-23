"use client";

import { useCallback, useEffect, useState } from "react";
import { getImportRun, mailErrorMessage, type ImportRun } from "@/lib/api/mail";

export function useImportRun(runId: string) {
  const [run, setRun] = useState<ImportRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const result = await getImportRun(runId, controller.signal);
        if (controller.signal.aborted) return;
        setRun(result);
        setError(null);
        if (result.status === "queued" || result.status === "running") {
          timer = setTimeout(poll, 1_000);
        }
      } catch (reason) {
        if (!controller.signal.aborted) setError(mailErrorMessage(reason));
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [runId, version]);

  return { run, error, refresh };
}
