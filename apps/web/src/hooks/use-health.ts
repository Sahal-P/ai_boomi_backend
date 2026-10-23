"use client";

import { useCallback, useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

type ConnectionState =
  | { state: "checking" }
  | { state: "connected" | "degraded"; health: HealthResponse; checkedAt: Date }
  | { state: "offline"; checkedAt: Date };

export function useHealth() {
  const [connection, setConnection] = useState<ConnectionState>({
    state: "checking",
  });
  const [requestVersion, setRequestVersion] = useState(0);

  const refresh = useCallback(() => {
    setConnection({ state: "checking" });
    setRequestVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void getHealth(controller.signal).then(
      (health) => {
        if (!controller.signal.aborted) {
          setConnection({
            state: health.status === "ok" ? "connected" : "degraded",
            health,
            checkedAt: new Date(),
          });
        }
      },
      () => {
        if (!controller.signal.aborted) {
          setConnection({ state: "offline", checkedAt: new Date() });
        }
      },
    );
    return () => controller.abort();
  }, [requestVersion]);

  useEffect(() => {
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  return { connection, refresh };
}
