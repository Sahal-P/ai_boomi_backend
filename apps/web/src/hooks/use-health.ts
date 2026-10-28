"use client";

import { useCallback, useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api/health";
import { checkHealth } from "@/lib/health-check";

type ConnectionState =
  | { state: "checking" }
  | { state: "connected" | "degraded"; health: HealthResponse; checkedAt: Date }
  | { state: "offline"; checkedAt: Date };

export function useHealth() {
  const [connection, setConnection] = useState<ConnectionState>({
    state: "checking",
  });
  const [requestVersion, setRequestVersion] = useState(0);

  // A routine re-check keeps showing the last result until the new one arrives.
  const refresh = useCallback(() => {
    setRequestVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void checkHealth(getHealth, controller.signal).then(
      (health) => {
        if (controller.signal.aborted) return;
        setConnection(
          health
            ? {
                state: health.status === "ok" ? "connected" : "degraded",
                health,
                checkedAt: new Date(),
              }
            : { state: "offline", checkedAt: new Date() },
        );
      },
      () => undefined, // superseded or unmounted
    );
    return () => controller.abort();
  }, [requestVersion]);

  useEffect(() => {
    const interval = setInterval(refresh, 30_000);
    return () => clearInterval(interval);
  }, [refresh]);

  return { connection, refresh };
}
